"""Persistência de idempotência para escritas do data plane público.

A migração é explícita: este módulo não cria tabela no boot nem dentro de cada
request. Isso permite revisar e aprovar a alteração de schema antes da execução
em produção.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from flask import current_app, has_app_context

from ..config import config

DEFAULT_TTL_HOURS = 24


class IdempotencyConflict(ValueError):
    """A chave existe, mas foi reutilizada com parâmetros diferentes."""


class IdempotencyRecordUnavailable(RuntimeError):
    """A tabela ainda não foi migrada ou a persistência falhou."""


def _db_path() -> Path:
    if has_app_context():
        raw = current_app.config.get("AUTH_DB_PATH")
        if raw:
            return Path(str(raw))
    return config.auth_db_path


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    path = _db_path()
    try:
        conn = sqlite3.connect(str(path), timeout=30)
    except sqlite3.Error as exc:
        raise IdempotencyRecordUnavailable("Não foi possível abrir o banco de idempotência.") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise IdempotencyRecordUnavailable("Não foi possível persistir a idempotência.") from exc
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def request_hash(*parts: str) -> str:
    """Hash canônico de método/rota/payload já sanitizados."""
    canonical = "\n".join(str(part) for part in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def migrate() -> None:
    """Cria a tabela de idempotência; executar apenas por comando aprovado."""
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_idempotency (
                consumer_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,
                status_code INTEGER,
                response_json TEXT,
                resource_id TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (consumer_id, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS idx_api_idempotency_expires_at
                ON api_idempotency(expires_at);
            """
        )


def _cleanup_expired(conn: sqlite3.Connection, now: str) -> None:
    conn.execute("DELETE FROM api_idempotency WHERE expires_at <= ?", (now,))


def reserve(
    consumer_id: str,
    key: str,
    fingerprint: str,
    *,
    resource_id: str | None = None,
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> dict[str, Any] | None:
    """Reserva a chave ou devolve a decisão anterior.

    Retorno ``None`` significa que a chave foi reservada pelo request atual.
    Um dicionário significa replay da decisão anterior. Conflito de fingerprint
    levanta ``IdempotencyConflict``.
    """
    clean_consumer = str(consumer_id).strip()
    clean_key = str(key).strip()
    if not clean_consumer or not clean_key:
        raise ValueError("consumer_id e idempotency_key são obrigatórios.")
    now = _now()
    expires = now + timedelta(hours=max(1, int(ttl_hours)))
    now_iso = _iso(now)
    with _conn() as conn:
        _cleanup_expired(conn, now_iso)
        try:
            conn.execute(
                """
                INSERT INTO api_idempotency (
                    consumer_id, idempotency_key, request_hash, resource_id, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (clean_consumer, clean_key, fingerprint, resource_id, now_iso, _iso(expires)),
            )
            return None
        except sqlite3.IntegrityError:
            row = conn.execute(
                """
                SELECT request_hash, status_code, response_json, resource_id
                  FROM api_idempotency
                 WHERE consumer_id = ? AND idempotency_key = ?
                 LIMIT 1
                """,
                (clean_consumer, clean_key),
            ).fetchone()
            if not row:
                raise IdempotencyRecordUnavailable("Registro de idempotência desapareceu durante o retry.")
            if row["request_hash"] != fingerprint:
                raise IdempotencyConflict("A Idempotency-Key foi usada com parâmetros diferentes.")
            if row["status_code"] is None or not row["response_json"]:
                # Outro request ainda está criando o recurso. O cliente deve
                # repetir depois, sem disparar um segundo job.
                return {
                    "status_code": 409,
                    "response": {
                        "code": "REQUEST_IN_PROGRESS",
                        "detail": "A operação com esta Idempotency-Key ainda está em andamento.",
                    },
                    "resource_id": row["resource_id"],
                }
            try:
                response = json.loads(row["response_json"])
            except json.JSONDecodeError as exc:
                raise IdempotencyRecordUnavailable("Registro de idempotência inválido.") from exc
            return {
                "status_code": int(row["status_code"]),
                "response": response,
                "resource_id": row["resource_id"],
            }


def release(consumer_id: str, key: str) -> None:
    """Libera uma reserva quando o recurso não foi aceito na fila."""
    with _conn() as conn:
        conn.execute(
            "DELETE FROM api_idempotency WHERE consumer_id = ? AND idempotency_key = ? AND status_code IS NULL",
            (str(consumer_id).strip(), str(key).strip()),
        )


def record(
    consumer_id: str,
    key: str,
    *,
    status_code: int,
    response: dict[str, Any],
    resource_id: str | None = None,
) -> None:
    """Grava a resposta segura que será reproduzida em retries."""
    with _conn() as conn:
        result = conn.execute(
            """
            UPDATE api_idempotency
               SET status_code = ?, response_json = ?, resource_id = ?
             WHERE consumer_id = ? AND idempotency_key = ?
            """,
            (
                int(status_code),
                json.dumps(response, ensure_ascii=False, separators=(",", ":")),
                resource_id,
                str(consumer_id).strip(),
                str(key).strip(),
            ),
        )
        if result.rowcount != 1:
            raise IdempotencyRecordUnavailable("Registro de idempotência não encontrado para gravação.")
