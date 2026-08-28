"""Chaves de liberação para consumo externo do Ecossistema Viral.

Essas chaves são usadas para abrir acesso ao SaaS / API pública com vencimento
definido. O valor completo só é exibido na criação; o restante do fluxo trabalha
com hash, data de expiração e revogação.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from flask import current_app, has_app_context

from ..config import config

KEY_PREFIX = "mago_"
KNOWN_SCOPES = {
    "catalog:read",
    "transcribe:write",
    "jobs:read",
    "jobs:write",
    "results:read",
    "usage:read",
    "public",
    "admin",
}


def _db_path() -> Path:
    if not has_app_context():
        return config.auth_db_path
    raw = current_app.config.get("AUTH_DB_PATH")
    if not raw:
        return config.auth_db_path
    return Path(str(raw))


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _prefix(raw_key: str) -> str:
    if len(raw_key) <= 16:
        return raw_key
    return f"{raw_key[:10]}…{raw_key[-6:]}"


def migrate() -> None:
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS release_keys (
                id TEXT PRIMARY KEY,
                account_id TEXT,
                label TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                secret_hash TEXT NOT NULL UNIQUE,
                scopes_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                created_by TEXT,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                last_used_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_release_keys_expires_at ON release_keys(expires_at);
            CREATE INDEX IF NOT EXISTS idx_release_keys_revoked_at ON release_keys(revoked_at);
            CREATE INDEX IF NOT EXISTS idx_release_keys_secret_hash ON release_keys(secret_hash);
            """
        )
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(release_keys)").fetchall()}
        if "account_id" not in columns:
            conn.execute("ALTER TABLE release_keys ADD COLUMN account_id TEXT")
        conn.execute("UPDATE release_keys SET account_id = id WHERE account_id IS NULL OR account_id = ''")


def _public(row: sqlite3.Row) -> dict[str, Any]:
    scopes = []
    try:
        scopes = list(json.loads(row["scopes_json"] or "[]"))
    except Exception:
        scopes = []

    expires_at = _dt(row["expires_at"])
    revoked_at = _dt(row["revoked_at"]) if row["revoked_at"] else None
    now = datetime.now(timezone.utc)
    status = "revoked" if revoked_at else ("expired" if expires_at <= now else "active")
    return {
        "id": row["id"],
        "label": row["label"],
        "prefix": row["key_prefix"],
        "scopes": scopes,
        "created_at": row["created_at"],
        "created_by": row["created_by"],
        "expires_at": row["expires_at"],
        "revoked_at": row["revoked_at"],
        "last_used_at": row["last_used_at"],
        "status": status,
        "expires_in_days": max(0, (expires_at.date() - now.date()).days),
    }


def list_keys() -> list[dict[str, Any]]:
    migrate()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM release_keys ORDER BY created_at DESC, label ASC"
        ).fetchall()
        return [_public(row) for row in rows]


def _normalize_scopes(scopes: Any) -> list[str]:
    if isinstance(scopes, str):
        raw = [part.strip() for part in scopes.split(",")]
        return [scope for scope in raw if scope]
    if isinstance(scopes, list):
        return [str(scope).strip() for scope in scopes if str(scope).strip()]
    return []


def create_key(
    actor: dict[str, Any],
    *,
    label: str,
    expires_in_days: int,
    scopes: Any = None,
) -> dict[str, Any]:
    migrate()
    if actor.get("role") != "owner":
        raise PermissionError("Sem permissão para gerar chaves de liberação.")

    clean_label = label.strip() or "Chave de liberação"
    if len(clean_label) < 3:
        raise ValueError("Informe um nome válido para a chave.")

    if expires_in_days < 1 or expires_in_days > 3650:
        raise ValueError("A validade precisa ficar entre 1 e 3650 dias.")

    clean_scopes = _normalize_scopes(scopes)
    unknown_scopes = sorted(set(clean_scopes) - KNOWN_SCOPES)
    if unknown_scopes:
        raise ValueError(f"Escopo(s) desconhecido(s): {', '.join(unknown_scopes)}.")
    token = f"{KEY_PREFIX}{secrets.token_urlsafe(32).replace('-', '').replace('_', '')}"
    now = _now()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat(
        timespec="seconds"
    )
    key_id = f"rk_{secrets.token_hex(12)}"
    secret_hash = _hash(token)

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO release_keys (
                id, account_id, label, key_prefix, secret_hash, scopes_json, created_at, created_by, expires_at,
                revoked_at, last_used_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                key_id,
                str(actor.get("id") or actor.get("email") or key_id),
                clean_label,
                _prefix(token),
                secret_hash,
                json.dumps(clean_scopes, ensure_ascii=False),
                now,
                f"{actor.get('email', '')} ({actor.get('id', '')})".strip(),
                expires_at,
            ),
        )
        row = conn.execute("SELECT * FROM release_keys WHERE id = ? LIMIT 1", (key_id,)).fetchone()
        if not row:
            raise RuntimeError("Falha ao registrar a chave de liberação.")

    public = _public(row)
    public["raw_key"] = token
    public["raw_key_once"] = token
    return public


def revoke_key(actor: dict[str, Any], key_id: str) -> dict[str, Any]:
    migrate()
    if actor.get("role") != "owner":
        raise PermissionError("Sem permissão para revogar chaves.")

    with _conn() as conn:
        row = conn.execute("SELECT * FROM release_keys WHERE id = ? LIMIT 1", (key_id,)).fetchone()
        if not row:
            raise ValueError("Chave não encontrada.")
        if row["revoked_at"]:
            return _public(row)
        now = _now()
        conn.execute("UPDATE release_keys SET revoked_at = ? WHERE id = ?", (now, key_id))
        row = conn.execute("SELECT * FROM release_keys WHERE id = ? LIMIT 1", (key_id,)).fetchone()
        if not row:
            raise RuntimeError("Falha ao revogar a chave.")
        return _public(row)


def validate_key(raw_key: str) -> dict[str, Any] | None:
    key = raw_key.strip()
    if not key:
        return None

    migrate()
    hashed = _hash(key)
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM release_keys WHERE secret_hash = ? LIMIT 1",
            (hashed,),
        ).fetchone()
        if not row:
            return None

        now = datetime.now(timezone.utc)
        expires_at = _dt(row["expires_at"])
        if row["revoked_at"] or expires_at <= now:
            return None

        conn.execute(
            "UPDATE release_keys SET last_used_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        public = _public(row)
        public["account_id"] = row["account_id"] or row["id"]
        public["valid"] = True
        return public
