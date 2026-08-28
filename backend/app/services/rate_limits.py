"""Rate limit, quota diária e orçamento de custo por consumidor.

O módulo é deliberadamente conservador: a reserva acontece depois da
autenticação e antes de enfileirar o trabalho. Se o enqueue falhar, a reserva é
liberada. O custo aqui é uma unidade interna estimada, não uma fatura do
provider; valores reais devem ser reconciliados por um ledger posterior.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from flask import current_app, has_app_context, make_response

from ..config import config

DEFAULT_REQUESTS_PER_MINUTE = 60
DEFAULT_JOBS_PER_DAY = 100
DEFAULT_AUDIO_SECONDS_PER_DAY = 3600
DEFAULT_COST_UNITS_PER_DAY = 3600


class LimitExceeded(RuntimeError):
    def __init__(self, code: str, retry_after_seconds: int, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        self.detail = detail


class UsageUnavailable(RuntimeError):
    pass


def enforce():
    """Limita requests autenticadas e adiciona headers de quota."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            from .api_auth import current_api_key, problem_response

            consumer_id = str(current_api_key()["id"])
            try:
                record_request(consumer_id)
            except LimitExceeded as exc:
                response = problem_response(
                    429,
                    exc.code,
                    exc.detail,
                    retryable=True,
                    retry_after_seconds=exc.retry_after_seconds,
                )
                response.headers["X-RateLimit-Limit"] = str(limits(consumer_id)["requests_per_minute"])
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(time.time()) + _retry_after_minute())
                return response
            except UsageUnavailable:
                return problem_response(503, "USAGE_STORE_UNAVAILABLE", "O ledger de uso está temporariamente indisponível.", retryable=True, retry_after_seconds=5)

            response = make_response(view(*args, **kwargs))
            try:
                current = snapshot(consumer_id)
                response.headers["X-RateLimit-Limit"] = str(current["limits"]["requests_per_minute"])
                response.headers["X-RateLimit-Remaining"] = str(max(0, current["limits"]["requests_per_minute"] - current["requests"]))
                response.headers["X-RateLimit-Reset"] = str(int(time.time()) + _retry_after_minute())
                response.headers["X-Quota-Jobs-Limit"] = str(current["limits"]["jobs_per_day"])
                response.headers["X-Quota-Jobs-Used"] = str(current["jobs"])
                response.headers["X-Quota-Audio-Seconds-Limit"] = str(current["limits"]["audio_seconds_per_day"])
                response.headers["X-Quota-Audio-Seconds-Used"] = str(current["audio_seconds"])
                response.headers["X-Quota-Cost-Units-Limit"] = str(current["limits"]["cost_units_per_day"])
                response.headers["X-Quota-Cost-Units-Used"] = str(current["cost_units"])
            except UsageUnavailable:
                pass
            return response

        return wrapped
    return decorator


def _db_path() -> Path:
    if has_app_context():
        raw = current_app.config.get("AUTH_DB_PATH")
        if raw:
            return Path(str(raw))
    return config.auth_db_path


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(str(_db_path()), timeout=30)
    except sqlite3.Error as exc:
        raise UsageUnavailable("Não foi possível abrir o ledger de uso.") from exc
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise UsageUnavailable("Não foi possível persistir o uso da API.") from exc
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _day_start(now: datetime | None = None) -> str:
    current = now or _now()
    return _iso(current.replace(hour=0, minute=0, second=0, microsecond=0))


def _minute_start(now: datetime | None = None) -> str:
    current = now or _now()
    return _iso(current.replace(second=0, microsecond=0))


def _limit_int(name: str, default: int) -> int:
    try:
        return max(1, int(__import__("os").environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


def limits(consumer_id: str | None = None) -> dict[str, int]:
    defaults = {
        "requests_per_minute": _limit_int("API_REQUESTS_PER_MINUTE", DEFAULT_REQUESTS_PER_MINUTE),
        "jobs_per_day": _limit_int("API_JOBS_PER_DAY", DEFAULT_JOBS_PER_DAY),
        "audio_seconds_per_day": _limit_int("API_AUDIO_SECONDS_PER_DAY", DEFAULT_AUDIO_SECONDS_PER_DAY),
        "cost_units_per_day": _limit_int("API_COST_UNITS_PER_DAY", DEFAULT_COST_UNITS_PER_DAY),
        "max_concurrent_jobs": _limit_int("API_MAX_CONCURRENT_JOBS", 2),
    }
    if not consumer_id:
        return defaults
    try:
        from . import billing
        account_id = billing.account_id_for_consumer(str(consumer_id))
        return billing.limits_for(account_id)
    except Exception:
        # Compatibilidade durante rollout: a migração de billing é explícita.
        return defaults


def migrate() -> None:
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                units REAL NOT NULL DEFAULT 0,
                job_id TEXT,
                idempotency_key TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_api_usage_consumer_time
                ON api_usage_events(consumer_id, created_at);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_api_usage_idempotency
                ON api_usage_events(consumer_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL;
            """
        )


def _sum(conn: sqlite3.Connection, consumer_id: str, kind: str, start: str) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(units), 0) AS total
          FROM api_usage_events
         WHERE consumer_id = ? AND kind = ? AND created_at >= ?
        """,
        (str(consumer_id), str(kind), start),
    ).fetchone()
    return float(row["total"] if row else 0)


def _active_count(conn: sqlite3.Connection, consumer_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM api_usage_events WHERE consumer_id = ? AND kind = 'active_job'",
        (str(consumer_id),),
    ).fetchone()
    return int(row["total"] if row else 0)


def snapshot(consumer_id: str) -> dict[str, Any]:
    check_ready()
    now = _now()
    with _conn() as conn:
        request_count = _sum(conn, consumer_id, "request", _minute_start(now))
        jobs_count = _sum(conn, consumer_id, "job", _day_start(now))
        audio_seconds = _sum(conn, consumer_id, "audio_seconds", _day_start(now))
        cost_units = _sum(conn, consumer_id, "cost_units", _day_start(now))
        active_jobs = _active_count(conn, consumer_id)
    configured = limits(consumer_id)
    return {
        "period": "utc",
        "minute_started_at": _minute_start(now),
        "day_started_at": _day_start(now),
        "requests": int(request_count),
        "jobs": int(jobs_count),
        "audio_seconds": int(audio_seconds),
        "cost_units": round(cost_units, 3),
        "active_jobs": active_jobs,
        "limits": configured,
    }


def _retry_after_minute(now: datetime | None = None) -> int:
    current = now or _now()
    return max(1, int(60 - current.second))


def record_request(consumer_id: str) -> dict[str, Any]:
    """Conta a requisição autenticada e aplica limite fixo por minuto."""
    check_ready()
    now = _now()
    start = _minute_start(now)
    configured = limits(consumer_id)
    with _conn() as conn:
        count = _sum(conn, consumer_id, "request", start)
        if count >= configured["requests_per_minute"]:
            raise LimitExceeded(
                "RATE_LIMIT_EXCEEDED",
                _retry_after_minute(now),
                "Limite de requisições por minuto atingido para esta API key.",
            )
        conn.execute(
            "INSERT INTO api_usage_events (consumer_id, kind, units, created_at) VALUES (?, 'request', 1, ?)",
            (str(consumer_id), _iso(now)),
        )
    return snapshot(consumer_id)


def reserve_job(
    consumer_id: str,
    *,
    job_id: str,
    idempotency_key: str,
    audio_seconds: float,
    cost_units: float,
) -> dict[str, Any]:
    """Reserva job/custo atomicamente; a chave de idempotência evita cobrança dupla."""
    check_ready()
    now = _now()
    configured = limits(consumer_id)
    audio = max(0.0, float(audio_seconds))
    cost = max(0.0, float(cost_units))
    with _conn() as conn:
        existing = conn.execute(
            """
            SELECT job_id FROM api_usage_events
             WHERE consumer_id = ? AND idempotency_key = ? LIMIT 1
            """,
            (str(consumer_id), str(idempotency_key)),
        ).fetchone()
        if existing:
            return snapshot(consumer_id)

        active_row = conn.execute(
            "SELECT COUNT(*) AS total FROM api_usage_events WHERE consumer_id = ? AND kind = 'active_job'",
            (str(consumer_id),),
        ).fetchone()
        active_jobs = int(active_row["total"] if active_row else 0)
        if active_jobs >= configured["max_concurrent_jobs"]:
            raise LimitExceeded(
                "CONCURRENT_JOB_LIMIT_EXCEEDED",
                30,
                "Limite de jobs concorrentes atingido para esta API key.",
            )

        jobs_count = _sum(conn, consumer_id, "job", _day_start(now))
        audio_used = _sum(conn, consumer_id, "audio_seconds", _day_start(now))
        cost_used = _sum(conn, consumer_id, "cost_units", _day_start(now))
        if jobs_count >= configured["jobs_per_day"]:
            raise LimitExceeded("DAILY_JOB_QUOTA_EXCEEDED", 3600, "Quota diária de jobs atingida para esta API key.")
        if audio_used + audio > configured["audio_seconds_per_day"]:
            raise LimitExceeded("DAILY_AUDIO_QUOTA_EXCEEDED", 3600, "Quota diária de áudio atingida para esta API key.")
        if cost_used + cost > configured["cost_units_per_day"]:
            raise LimitExceeded("DAILY_COST_LIMIT_EXCEEDED", 3600, "Orçamento diário estimado atingido para esta API key.")

        created = _iso(now)
        conn.execute(
            """
            INSERT INTO api_usage_events (consumer_id, kind, units, job_id, idempotency_key, created_at)
            VALUES (?, 'job', 1, ?, ?, ?)
            """,
            (str(consumer_id), str(job_id), str(idempotency_key), created),
        )
        conn.execute(
            """
            INSERT INTO api_usage_events (consumer_id, kind, units, job_id, idempotency_key, created_at)
            VALUES (?, 'active_job', 1, ?, NULL, ?)
            """,
            (str(consumer_id), str(job_id), created),
        )
        conn.execute(
            """
            INSERT INTO api_usage_events (consumer_id, kind, units, job_id, idempotency_key, created_at)
            VALUES (?, 'audio_seconds', ?, ?, NULL, ?)
            """,
            (str(consumer_id), audio, str(job_id), created),
        )
        conn.execute(
            """
            INSERT INTO api_usage_events (consumer_id, kind, units, job_id, idempotency_key, created_at)
            VALUES (?, 'cost_units', ?, ?, NULL, ?)
            """,
            (str(consumer_id), cost, str(job_id), created),
        )
    return snapshot(consumer_id)


def release_active_job(consumer_id: str, *, job_id: str) -> None:
    """Libera a vaga de concorrência quando o job deixa de estar ativo."""
    check_ready()
    with _conn() as conn:
        conn.execute(
            "DELETE FROM api_usage_events WHERE consumer_id = ? AND job_id = ? AND kind = 'active_job'",
            (str(consumer_id), str(job_id)),
        )


def release_job(consumer_id: str, *, job_id: str, idempotency_key: str) -> None:
    """Reverte a reserva quando o job não foi aceito na fila."""
    check_ready()
    with _conn() as conn:
        conn.execute(
            """
            DELETE FROM api_usage_events
             WHERE consumer_id = ? AND job_id = ?
               AND (idempotency_key = ? OR idempotency_key IS NULL)
            """,
            (str(consumer_id), str(job_id), str(idempotency_key)),
        )


def check_ready() -> None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'api_usage_events' LIMIT 1"
        ).fetchone()
        if not row:
            raise UsageUnavailable("O ledger de uso ainda não foi migrado.")


def usage(consumer_id: str) -> dict[str, Any]:
    return snapshot(consumer_id)
