"""Billing, planos e quotas comerciais do data plane.

A conta comercial é separada da API key, mas a v1 usa o owner da chave como
``account_id`` até existir uma entidade de organização no painel. Nenhum valor
monetário é calculado aqui: o módulo controla entitlements e consumo técnico.
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

PLAN_CATALOG: dict[str, dict[str, Any]] = {
    "starter": {
        "code": "starter",
        "name": "Starter",
        "monthly_audio_minutes": 60,
        "monthly_clips": 100,
        "storage_bytes": 5 * 1024**3,
        "requests_per_minute": 60,
        "jobs_per_day": 100,
        "audio_seconds_per_day": 3600,
        "cost_units_per_day": 3600,
        "max_concurrent_jobs": 2,
    },
    "pro": {
        "code": "pro",
        "name": "Pro",
        "monthly_audio_minutes": 600,
        "monthly_clips": 1000,
        "storage_bytes": 50 * 1024**3,
        "requests_per_minute": 180,
        "jobs_per_day": 1000,
        "audio_seconds_per_day": 36000,
        "cost_units_per_day": 36000,
        "max_concurrent_jobs": 8,
    },
    "agency": {
        "code": "agency",
        "name": "Agency",
        "monthly_audio_minutes": 3000,
        "monthly_clips": 10000,
        "storage_bytes": 250 * 1024**3,
        "requests_per_minute": 600,
        "jobs_per_day": 5000,
        "audio_seconds_per_day": 180000,
        "cost_units_per_day": 180000,
        "max_concurrent_jobs": 24,
    },
}

ACTIVE_STATUSES = {"trialing", "active"}
BLOCKED_STATUSES = {"canceled", "cancelled", "unpaid", "incomplete_expired", "past_due", "paused"}


class BillingLimitExceeded(RuntimeError):
    def __init__(self, code: str, detail: str, *, retryable: bool = False) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable
        self.retry_after_seconds = 3600


class BillingUnavailable(RuntimeError):
    pass


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
        raise BillingUnavailable("Não foi possível abrir o armazenamento de billing.") from exc
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    except sqlite3.Error as exc:
        conn.rollback()
        raise BillingUnavailable("Não foi possível persistir o billing.") from exc
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def current_period(now: datetime | None = None) -> tuple[str, str]:
    value = now or _now()
    start = value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        next_start = start.replace(year=start.year + 1, month=1)
    else:
        next_start = start.replace(month=start.month + 1)
    return _iso(start), _iso(next_start)


def migrate() -> None:
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS billing_accounts (
                account_id TEXT PRIMARY KEY,
                plan_code TEXT NOT NULL DEFAULT 'starter',
                subscription_status TEXT NOT NULL DEFAULT 'active',
                provider TEXT,
                provider_customer_id TEXT,
                provider_subscription_id TEXT,
                current_period_start TEXT NOT NULL,
                current_period_end TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_billing_accounts_provider_subscription
                ON billing_accounts(provider, provider_subscription_id);
            CREATE TABLE IF NOT EXISTS billing_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                units REAL NOT NULL DEFAULT 0,
                resource_id TEXT,
                idempotency_key TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(account_id, kind, idempotency_key)
            );
            CREATE INDEX IF NOT EXISTS idx_billing_usage_account_time
                ON billing_usage_events(account_id, created_at);
            CREATE TABLE IF NOT EXISTS billing_storage_reservations (
                resource_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                bytes INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                released_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_billing_storage_account_status
                ON billing_storage_reservations(account_id, status);
            CREATE TABLE IF NOT EXISTS billing_webhook_events (
                provider TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                account_id TEXT,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'received',
                received_at TEXT NOT NULL,
                processed_at TEXT,
                PRIMARY KEY(provider, event_id)
            );
            """
        )


def _plan(code: str) -> dict[str, Any]:
    return dict(PLAN_CATALOG.get(str(code).lower(), PLAN_CATALOG["starter"]))


def ensure_account(account_id: str, *, email: str | None = None) -> dict[str, Any]:
    account_id = str(account_id)
    start, end = current_period()
    now = _iso(_now())
    with _conn() as conn:
        row = conn.execute("SELECT * FROM billing_accounts WHERE account_id = ?", (account_id,)).fetchone()
        if not row:
            metadata = {"email": email} if email else {}
            conn.execute(
                """
                INSERT INTO billing_accounts (
                    account_id, plan_code, subscription_status, current_period_start,
                    current_period_end, metadata_json, created_at, updated_at
                ) VALUES (?, 'starter', 'active', ?, ?, ?, ?, ?)
                """,
                (account_id, start, end, json.dumps(metadata, ensure_ascii=False), now, now),
            )
            row = conn.execute("SELECT * FROM billing_accounts WHERE account_id = ?", (account_id,)).fetchone()
    return _account_public(row)


def _account_public(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise BillingUnavailable("Conta comercial não encontrada.")
    plan = _plan(str(row["plan_code"]))
    return {
        "account_id": row["account_id"],
        "plan": {key: value for key, value in plan.items()},
        "subscription_status": row["subscription_status"],
        "provider": row["provider"],
        "provider_customer_id": row["provider_customer_id"],
        "provider_subscription_id": row["provider_subscription_id"],
        "current_period_start": row["current_period_start"],
        "current_period_end": row["current_period_end"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def account(account_id: str) -> dict[str, Any]:
    return ensure_account(account_id)


def account_id_for_consumer(consumer_id: str) -> str:
    """Resolve a API key técnica para o tenant comercial associado."""
    try:
        with _conn() as conn:
            row = conn.execute("SELECT account_id FROM release_keys WHERE id = ? LIMIT 1", (str(consumer_id),)).fetchone()
            if row and row["account_id"]:
                return str(row["account_id"])
    except BillingUnavailable:
        pass
    return str(consumer_id)


def plan_for(account_id: str) -> dict[str, Any]:
    return _plan(ensure_account(account_id)["plan"]["code"])


def limits_for(account_id: str) -> dict[str, int]:
    plan = plan_for(account_id)
    return {
        "requests_per_minute": int(plan["requests_per_minute"]),
        "jobs_per_day": int(plan["jobs_per_day"]),
        "audio_seconds_per_day": int(plan["audio_seconds_per_day"]),
        "cost_units_per_day": int(plan["cost_units_per_day"]),
        "max_concurrent_jobs": int(plan["max_concurrent_jobs"]),
    }


def set_subscription(
    account_id: str,
    *,
    plan_code: str,
    status: str,
    provider: str | None = None,
    provider_customer_id: str | None = None,
    provider_subscription_id: str | None = None,
    current_period_start: str | None = None,
    current_period_end: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if plan_code not in PLAN_CATALOG:
        raise ValueError("Plano desconhecido.")
    existing = ensure_account(account_id)
    start, end = current_period()
    now = _iso(_now())
    with _conn() as conn:
        conn.execute(
            """
            UPDATE billing_accounts
               SET plan_code = ?, subscription_status = ?, provider = ?,
                   provider_customer_id = ?, provider_subscription_id = ?,
                   current_period_start = ?, current_period_end = ?,
                   metadata_json = ?, updated_at = ?
             WHERE account_id = ?
            """,
            (
                plan_code,
                str(status).lower(),
                provider,
                provider_customer_id,
                provider_subscription_id,
                current_period_start or existing["current_period_start"] or start,
                current_period_end or existing["current_period_end"] or end,
                json.dumps(metadata or {}, ensure_ascii=False),
                now,
                str(account_id),
            ),
        )
        row = conn.execute("SELECT * FROM billing_accounts WHERE account_id = ?", (str(account_id),)).fetchone()
    return _account_public(row)


def record_webhook_event(
    provider: str,
    event_id: str,
    event_type: str,
    *,
    account_id: str | None,
    payload_hash: str,
) -> bool:
    try:
        with _conn() as conn:
            conn.execute(
                """
                INSERT INTO billing_webhook_events
                    (provider, event_id, event_type, account_id, payload_hash, received_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (provider, event_id, event_type, account_id, payload_hash, _iso(_now())),
            )
        return True
    except BillingUnavailable:
        raise
    except sqlite3.IntegrityError:
        return False


def mark_webhook_processed(provider: str, event_id: str, *, status: str = "processed") -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE billing_webhook_events SET status = ?, processed_at = ? WHERE provider = ? AND event_id = ?",
            (status, _iso(_now()), provider, event_id),
        )


def _period_for(account_id: str) -> tuple[str, str]:
    row = ensure_account(account_id)
    return str(row["current_period_start"]), str(row["current_period_end"])


def _usage_sum(conn: sqlite3.Connection, account_id: str, kind: str, start: str, end: str) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(units), 0) AS total
          FROM billing_usage_events
         WHERE account_id = ? AND kind = ? AND created_at >= ? AND created_at < ?
        """,
        (str(account_id), kind, start, end),
    ).fetchone()
    return float(row["total"] if row else 0.0)


def _storage_used(conn: sqlite3.Connection, account_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(bytes), 0) AS total FROM billing_storage_reservations WHERE account_id = ? AND status = 'active'",
        (str(account_id),),
    ).fetchone()
    return int(row["total"] if row else 0)


def usage_snapshot(account_id: str) -> dict[str, Any]:
    info = ensure_account(account_id)
    plan = info["plan"]
    start, end = str(info["current_period_start"]), str(info["current_period_end"])
    with _conn() as conn:
        minutes = _usage_sum(conn, account_id, "transcription_minutes", start, end)
        clips = _usage_sum(conn, account_id, "clip_count", start, end)
        storage = _storage_used(conn, account_id)
    minute_limit = float(plan["monthly_audio_minutes"])
    clip_limit = int(plan["monthly_clips"])
    storage_limit = int(plan["storage_bytes"])
    return {
        "account_id": account_id,
        "plan": plan,
        "subscription_status": info["subscription_status"],
        "period_start": start,
        "period_end": end,
        "used": {
            "audio_minutes": round(minutes, 3),
            "clips": int(clips),
            "storage_bytes": storage,
        },
        "limits": {
            "audio_minutes": minute_limit,
            "clips": clip_limit,
            "storage_bytes": storage_limit,
        },
        "remaining": {
            "audio_minutes": round(max(0.0, minute_limit - minutes), 3),
            "clips": max(0, clip_limit - int(clips)),
            "storage_bytes": max(0, storage_limit - storage),
        },
    }


def reserve_transcription(account_id: str, *, seconds: float, storage_bytes: int, resource_id: str, idempotency_key: str) -> None:
    info = ensure_account(account_id)
    if str(info["subscription_status"]).lower() in BLOCKED_STATUSES:
        raise BillingLimitExceeded("SUBSCRIPTION_INACTIVE", "A assinatura não está ativa para novos jobs.")
    snapshot = usage_snapshot(account_id)
    minutes = max(0.0, float(seconds)) / 60.0
    if minutes > snapshot["remaining"]["audio_minutes"]:
        raise BillingLimitExceeded("MONTHLY_AUDIO_QUOTA_EXCEEDED", "A quota mensal de minutos do plano foi atingida.")
    if int(storage_bytes) > snapshot["remaining"]["storage_bytes"]:
        raise BillingLimitExceeded("STORAGE_QUOTA_EXCEEDED", "A quota de armazenamento do plano foi atingida.")
    with _conn() as conn:
        try:
            conn.execute(
                "INSERT INTO billing_usage_events (account_id, kind, units, resource_id, idempotency_key, created_at) VALUES (?, 'transcription_minutes', ?, ?, ?, ?)",
                (str(account_id), minutes, str(resource_id), str(idempotency_key), _iso(_now())),
            )
            conn.execute(
                "INSERT INTO billing_storage_reservations (resource_id, account_id, bytes, status, created_at) VALUES (?, ?, ?, 'active', ?)",
                (str(resource_id), str(account_id), max(0, int(storage_bytes)), _iso(_now())),
            )
        except sqlite3.IntegrityError:
            return


def reserve_clip(account_id: str, *, resource_id: str, idempotency_key: str) -> None:
    info = ensure_account(account_id)
    if str(info["subscription_status"]).lower() in BLOCKED_STATUSES:
        raise BillingLimitExceeded("SUBSCRIPTION_INACTIVE", "A assinatura não está ativa para novos clips.")
    snapshot = usage_snapshot(account_id)
    if snapshot["remaining"]["clips"] < 1:
        raise BillingLimitExceeded("MONTHLY_CLIP_QUOTA_EXCEEDED", "A quota mensal de clips do plano foi atingida.")
    with _conn() as conn:
        try:
            conn.execute(
                "INSERT INTO billing_usage_events (account_id, kind, units, resource_id, idempotency_key, created_at) VALUES (?, 'clip_count', 1, ?, ?, ?)",
                (str(account_id), str(resource_id), str(idempotency_key), _iso(_now())),
            )
        except sqlite3.IntegrityError:
            return


def reserve_storage(account_id: str, *, resource_id: str, storage_bytes: int) -> None:
    info = ensure_account(account_id)
    snapshot = usage_snapshot(account_id)
    size = max(0, int(storage_bytes))
    if size > snapshot["remaining"]["storage_bytes"]:
        raise BillingLimitExceeded("STORAGE_QUOTA_EXCEEDED", "A quota de armazenamento do plano foi atingida.")
    with _conn() as conn:
        try:
            conn.execute(
                "INSERT INTO billing_storage_reservations (resource_id, account_id, bytes, status, created_at) VALUES (?, ?, ?, 'active', ?)",
                (str(resource_id), str(account_id), size, _iso(_now())),
            )
        except sqlite3.IntegrityError:
            return


def release_storage(account_id: str, *, resource_id: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE billing_storage_reservations SET status = 'released', released_at = ? WHERE account_id = ? AND resource_id = ? AND status = 'active'",
            (_iso(_now()), str(account_id), str(resource_id)),
        )


def release_reservation(account_id: str, *, resource_id: str, idempotency_key: str) -> None:
    """Desfaz somente a reserva de um job que não entrou na fila."""
    with _conn() as conn:
        conn.execute(
            "DELETE FROM billing_usage_events WHERE account_id = ? AND resource_id = ? AND idempotency_key = ?",
            (str(account_id), str(resource_id), str(idempotency_key)),
        )
        conn.execute(
            "DELETE FROM billing_storage_reservations WHERE account_id = ? AND resource_id = ? AND status = 'active'",
            (str(account_id), str(resource_id)),
        )
