"""Fila persistente para jobs do data plane.

A fila vive no mesmo banco protegido do control plane, mas não depende da fila
em memória do Gunicorn. O web process apenas grava uma intenção serializável; um
worker separado reivindica essa intenção com lease, heartbeat lógico e retries
limitados.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from flask import current_app, has_app_context

from ..config import config

DEFAULT_LEASE_SECONDS = 900
DEFAULT_RETRY_DELAY_SECONDS = 30
DEFAULT_MAX_ATTEMPTS = 3


class QueueUnavailable(RuntimeError):
    """A fila não foi migrada ou não pode persistir um job."""


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
        raise QueueUnavailable("Não foi possível abrir a fila persistente.") from exc
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise QueueUnavailable("Não foi possível persistir a fila.") from exc
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def migrate() -> None:
    """Cria o schema da fila; deve ser chamado por migração explícita."""
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_queue (
                job_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                attempts INTEGER NOT NULL DEFAULT 0,
                available_at TEXT NOT NULL,
                locked_by TEXT,
                locked_at TEXT,
                lease_until TEXT,
                last_error_code TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_api_queue_ready
                ON api_queue(status, available_at, created_at);
            CREATE INDEX IF NOT EXISTS idx_api_queue_lease
                ON api_queue(status, lease_until);
            """
        )


def check_ready() -> None:
    """Falha rápido se o schema não foi criado pela migração controlada."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'api_queue' LIMIT 1"
        ).fetchone()
        if not row:
            raise QueueUnavailable("A fila persistente ainda não foi migrada.")


def enqueue(job_id: str, kind: str, payload: dict[str, Any]) -> bool:
    """Insere uma intenção serializável; repetir o job_id é idempotente."""
    now = _iso(_now())
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    check_ready()
    with _conn() as conn:
        try:
            conn.execute(
                """
                INSERT INTO api_queue (
                    job_id, kind, payload_json, status, available_at, created_at, updated_at
                ) VALUES (?, ?, ?, 'queued', ?, ?, ?)
                """,
                (str(job_id), str(kind), encoded, now, now, now),
            )
            return True
        except sqlite3.IntegrityError:
            row = conn.execute(
                "SELECT kind, payload_json FROM api_queue WHERE job_id = ? LIMIT 1",
                (str(job_id),),
            ).fetchone()
            if not row or row["kind"] != str(kind):
                raise QueueUnavailable("O job já existe com outro tipo de fila.")
            return False


def _requeue_expired_leases(conn: sqlite3.Connection, now_iso: str) -> None:
    conn.execute(
        """
        UPDATE api_queue
           SET status = 'queued', locked_by = NULL, locked_at = NULL,
               lease_until = NULL, available_at = ?, updated_at = ?
         WHERE status = 'running' AND lease_until IS NOT NULL AND lease_until <= ?
        """,
        (now_iso, now_iso, now_iso),
    )


def claim(
    worker_id: str,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    job_id: str | None = None,
) -> dict[str, Any] | None:
    """Reivindica atomicamente o próximo item pronto com um lease."""
    now = _now()
    now_iso = _iso(now)
    lease_until = _iso(now + timedelta(seconds=max(30, int(lease_seconds))))
    check_ready()
    with _conn() as conn:
        _requeue_expired_leases(conn, now_iso)
        query = """
            SELECT * FROM api_queue
             WHERE status = 'queued' AND available_at <= ?
        """
        params: tuple[Any, ...] = (now_iso,)
        if job_id:
            query += " AND job_id = ?"
            params = (now_iso, str(job_id))
        query += " ORDER BY created_at ASC LIMIT 1"
        row = conn.execute(query, params).fetchone()
        if not row:
            return None
        job_id = str(row["job_id"])
        changed = conn.execute(
            """
            UPDATE api_queue
               SET status = 'running', attempts = attempts + 1,
                   locked_by = ?, locked_at = ?, lease_until = ?, updated_at = ?
             WHERE job_id = ? AND status = 'queued'
            """,
            (str(worker_id), now_iso, lease_until, now_iso, job_id),
        )
        if changed.rowcount != 1:
            return None
        payload = json.loads(str(row["payload_json"]))
        return {
            "job_id": job_id,
            "kind": str(row["kind"]),
            "payload": payload,
            "attempts": int(row["attempts"]) + 1,
            "locked_by": str(worker_id),
            "lease_until": lease_until,
        }


def heartbeat(job_id: str, worker_id: str, *, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> bool:
    now = _now()
    now_iso = _iso(now)
    lease_until = _iso(now + timedelta(seconds=max(30, int(lease_seconds))))
    check_ready()
    with _conn() as conn:
        result = conn.execute(
            """
            UPDATE api_queue
               SET lease_until = ?, updated_at = ?
             WHERE job_id = ? AND status = 'running' AND locked_by = ?
            """,
            (lease_until, now_iso, str(job_id), str(worker_id)),
        )
        return result.rowcount == 1


def complete(job_id: str, worker_id: str | None = None) -> bool:
    check_ready()
    with _conn() as conn:
        if worker_id:
            result = conn.execute(
                """
                UPDATE api_queue
                   SET status = 'done', locked_by = NULL, locked_at = NULL,
                       lease_until = NULL, updated_at = ?
                 WHERE job_id = ? AND status = 'running' AND locked_by = ?
                """,
                (_iso(_now()), str(job_id), str(worker_id)),
            )
        else:
            result = conn.execute(
                """
                UPDATE api_queue
                   SET status = 'done', locked_by = NULL, locked_at = NULL,
                       lease_until = NULL, updated_at = ?
                 WHERE job_id = ?
                """,
                (_iso(_now()), str(job_id)),
            )
        return result.rowcount == 1


def fail(
    job_id: str,
    error_code: str,
    *,
    retryable: bool,
    worker_id: str | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SECONDS,
) -> bool:
    """Marca falha e, quando seguro, reencaminha com atraso limitado.

    Retorna ``True`` quando o job ficou terminal e ``False`` quando foi colocado
    novamente na fila.
    """
    now = _now()
    now_iso = _iso(now)
    check_ready()
    with _conn() as conn:
        row = conn.execute(
            "SELECT attempts FROM api_queue WHERE job_id = ? LIMIT 1", (str(job_id),)
        ).fetchone()
        if not row:
            return True
        attempts = int(row["attempts"])
        can_retry = bool(retryable) and attempts < max(1, int(max_attempts))
        if can_retry:
            available = _iso(now + timedelta(seconds=max(1, int(retry_delay_seconds))))
            values: tuple[Any, ...] = (available, str(error_code), now_iso, str(job_id))
            query = """
                UPDATE api_queue
                   SET status = 'queued', available_at = ?, last_error_code = ?,
                       locked_by = NULL, locked_at = NULL, lease_until = NULL, updated_at = ?
                 WHERE job_id = ?
            """
        else:
            values = (str(error_code), now_iso, str(job_id))
            query = """
                UPDATE api_queue
                   SET status = 'failed', last_error_code = ?,
                       locked_by = NULL, locked_at = NULL, lease_until = NULL, updated_at = ?
                 WHERE job_id = ?
            """
        if worker_id:
            query += " AND locked_by = ?"
            values = (*values, str(worker_id))
        result = conn.execute(query, values)
        if result.rowcount != 1:
            return True
        return not can_retry


def discard(job_id: str) -> bool:
    """Remove item ainda não executado durante rollback de aceitação."""
    check_ready()
    with _conn() as conn:
        result = conn.execute(
            "DELETE FROM api_queue WHERE job_id = ? AND status IN ('queued', 'failed')",
            (str(job_id),),
        )
        return result.rowcount == 1


def get(job_id: str) -> dict[str, Any] | None:
    check_ready()
    with _conn() as conn:
        row = conn.execute("SELECT * FROM api_queue WHERE job_id = ? LIMIT 1", (str(job_id),)).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["payload"] = json.loads(str(data.pop("payload_json")))
        except json.JSONDecodeError:
            data["payload"] = {}
        return data


def queue_depth() -> int:
    check_ready()
    with _conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM api_queue WHERE status = 'queued'").fetchone()
        return int(row["count"] if row else 0)
