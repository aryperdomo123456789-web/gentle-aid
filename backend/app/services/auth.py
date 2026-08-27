"""Autenticação e sessão do Ecossistema Viral.

Usuários e sessões ficam no SQLite do servidor, sem dependência do navegador
para manter login, histórico e permissões.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from flask import current_app, request
from werkzeug.security import check_password_hash, generate_password_hash

COOKIE_NAME = "viral_sid"
SESSION_TTL_DAYS = 30



def _bootstrap_users() -> list[dict[str, Any]]:
    """Retorna contas iniciais somente quando o operador as fornece por ambiente."""
    owner_email = os.environ.get("OWNER_EMAIL", "").strip().lower()
    owner_password = os.environ.get("OWNER_PASSWORD", "")
    if not owner_email or not owner_password:
        raise RuntimeError(
            "Banco de autenticação vazio: defina OWNER_EMAIL e OWNER_PASSWORD "
            "antes do primeiro boot; credenciais padrão não são permitidas."
        )
    if len(owner_password) < 12:
        raise RuntimeError("OWNER_PASSWORD precisa ter pelo menos 12 caracteres.")

    users = [
        {
            "id": "u_owner_mago",
            "email": owner_email,
            "name": os.environ.get("OWNER_NAME", "Mago").strip() or "Mago",
            "role": "owner",
            "password_hash": generate_password_hash(owner_password),
            "protected": 1,
        }
    ]

    demo_email = os.environ.get("DEMO_EMAIL", "").strip().lower()
    demo_password = os.environ.get("DEMO_PASSWORD", "")
    if demo_email or demo_password:
        if not demo_email or len(demo_password) < 12:
            raise RuntimeError(
                "DEMO_EMAIL e DEMO_PASSWORD devem ser definidos juntos; "
                "DEMO_PASSWORD precisa ter pelo menos 12 caracteres."
            )
        users.append(
            {
                "id": "u_common_demo",
                "email": demo_email,
                "name": os.environ.get("DEMO_NAME", "Operador").strip() or "Operador",
                "role": "common",
                "password_hash": generate_password_hash(demo_password),
                "protected": 0,
            }
        )
    return users


def _db_path() -> Path:
    raw = current_app.config.get("AUTH_DB_PATH")
    if not raw:
        from ..config import config

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


def _expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)).isoformat(timespec="seconds")


def migrate() -> None:
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS auth_users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('owner', 'common')),
                password_hash TEXT NOT NULL,
                protected INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES auth_users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at);
            """
        )
        _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    cursor = conn.execute("SELECT COUNT(*) AS total FROM auth_users")
    total = int(cursor.fetchone()["total"])
    if total:
        return

    now = _now()
    users = _bootstrap_users()
    conn.executemany(
        """
        INSERT INTO auth_users (
            id, email, name, role, password_hash, protected, created_at, updated_at, last_login_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                u["id"],
                u["email"].lower(),
                u["name"],
                u["role"],
                u["password_hash"],
                u["protected"],
                now,
                now,
                None,
            )
            for u in users
        ],
    )


def _public_user(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "role": row["role"],
        "protected": bool(row["protected"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_login_at": row["last_login_at"],
    }


def _row_user_by_id(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM auth_users WHERE id = ? LIMIT 1", (user_id,)).fetchone()


def _row_user_by_email(conn: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM auth_users WHERE lower(email) = lower(?) LIMIT 1",
        (email,),
    ).fetchone()


def _row_session(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT s.token, s.user_id, s.created_at, s.last_seen_at, s.expires_at
          FROM auth_sessions s
         WHERE s.token = ?
         LIMIT 1
        """,
        (token,),
    ).fetchone()


def _cookie_secure() -> bool:
    raw = current_app.config.get("AUTH_COOKIE_SECURE")
    if raw is None:
        return True
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def issue_session_cookie(response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="Lax",
        secure=_cookie_secure(),
        max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def current_session_token() -> str | None:
    token = request.cookies.get(COOKIE_NAME, "").strip()
    return token or None


def _load_current_session() -> dict[str, Any] | None:
    token = current_session_token()
    if not token:
        return None

    migrate()
    with _conn() as conn:
        session = _row_session(conn, token)
        if not session:
            conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            return None

        expires_at = datetime.fromisoformat(session["expires_at"])
        if expires_at <= datetime.now(timezone.utc):
            conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            return None

        conn.execute(
            "UPDATE auth_sessions SET last_seen_at = ?, expires_at = ? WHERE token = ?",
            (_now(), _expires_at(), token),
        )
        user = _row_user_by_id(conn, session["user_id"])
        if not user:
            conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            return None

        return {
            "token": token,
            "login_at": session["created_at"],
            "last_seen_at": session["last_seen_at"],
            "user": _public_user(user),
        }


def current_user() -> dict[str, Any] | None:
    session = _load_current_session()
    return session["user"] if session else None


def current_session() -> dict[str, Any] | None:
    return _load_current_session()


def login(email: str, password: str) -> tuple[dict[str, Any], str, str]:
    migrate()
    normalized_email = email.strip().lower()
    with _conn() as conn:
        user = _row_user_by_email(conn, normalized_email)
        if not user or not check_password_hash(user["password_hash"], password):
            raise ValueError("Credenciais inválidas. Verifique o acesso do dono ou do usuário.")

        now = _now()
        conn.execute(
            "UPDATE auth_users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user["id"]),
        )
        token = secrets.token_urlsafe(32)
        conn.execute(
            """
            INSERT INTO auth_sessions (token, user_id, created_at, last_seen_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (token, user["id"], now, now, _expires_at()),
        )
        row = _row_user_by_id(conn, user["id"])
        if not row:
            raise RuntimeError("Falha ao carregar o usuário logado.")
        return _public_user(row), token, now


def logout() -> None:
    token = current_session_token()
    if not token:
        return
    migrate()
    with _conn() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))


def list_users() -> list[dict[str, Any]]:
    migrate()
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM auth_users ORDER BY role DESC, created_at ASC").fetchall()
        return [_public_user(row) for row in rows]


def update_user(
    actor: dict[str, Any],
    target_id: str,
    *,
    name: str | None = None,
    email: str | None = None,
    password: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    migrate()
    with _conn() as conn:
        target = _row_user_by_id(conn, target_id)
        if not target:
            raise ValueError("Usuário não encontrado.")

        is_owner = actor.get("role") == "owner"
        is_self = actor.get("id") == target_id
        if not (is_owner or is_self):
            raise PermissionError("Sem permissão para editar outros usuários.")

        if target["protected"] and email and email.strip().lower() != target["email"].lower():
            raise PermissionError("O email do dono original é protegido.")

        if email:
            duplicate = _row_user_by_email(conn, email)
            if duplicate and duplicate["id"] != target_id:
                raise ValueError("Este email já está em uso.")

        next_name = (name or target["name"]).strip() or target["name"]
        next_email = target["email"] if target["protected"] else (email.strip().lower() if email else target["email"])
        next_role = target["role"] if target["protected"] else (role or target["role"])
        next_password_hash = target["password_hash"]
        if password:
            if len(password) < 6:
                raise ValueError("A nova senha precisa ter pelo menos 6 caracteres.")
            next_password_hash = generate_password_hash(password)

        now = _now()
        conn.execute(
            """
            UPDATE auth_users
               SET name = ?, email = ?, role = ?, password_hash = ?, updated_at = ?
             WHERE id = ?
            """,
            (next_name, next_email, next_role, next_password_hash, now, target_id),
        )
        row = _row_user_by_id(conn, target_id)
        if not row:
            raise RuntimeError("Falha ao atualizar o usuário.")
        return _public_user(row)


def create_user(
    actor: dict[str, Any],
    *,
    name: str,
    email: str,
    password: str,
    role: str = "common",
) -> dict[str, Any]:
    if actor.get("role") != "owner":
        raise PermissionError("Sem permissão para criar usuários.")
    if len(password) < 6:
        raise ValueError("A senha precisa ter pelo menos 6 caracteres.")

    migrate()
    normalized = email.strip().lower()
    with _conn() as conn:
        if _row_user_by_email(conn, normalized):
            raise ValueError("Este email já está em uso.")
        now = _now()
        user_id = f"u_{secrets.token_hex(12)}"
        conn.execute(
            """
            INSERT INTO auth_users (
                id, email, name, role, password_hash, protected, created_at, updated_at, last_login_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                normalized,
                name.strip() or normalized.split("@")[0] or "Usuário",
                "owner" if role == "owner" else "common",
                generate_password_hash(password),
                0,
                now,
                now,
                None,
            ),
        )
        row = _row_user_by_id(conn, user_id)
        if not row:
            raise RuntimeError("Falha ao criar o usuário.")
        return _public_user(row)


def delete_user(actor: dict[str, Any], target_id: str) -> None:
    migrate()
    with _conn() as conn:
        target = _row_user_by_id(conn, target_id)
        if not target:
            raise ValueError("Usuário não encontrado.")
        if actor.get("role") != "owner":
            raise PermissionError("Sem permissão para excluir usuários.")
        if actor.get("id") == target_id:
            raise PermissionError("Você não pode excluir a própria conta logada.")
        if target["protected"]:
            raise PermissionError("O dono original não pode ser excluído.")
        conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (target_id,))
        conn.execute("DELETE FROM auth_users WHERE id = ?", (target_id,))
