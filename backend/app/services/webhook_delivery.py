"""Entrega de eventos de jobs para endpoints do consumidor.

O segredo fica somente no meta protegido do job; nunca entra no envelope de
operação, log ou payload. Cada combinação job/evento é deduplicada no SQLite.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ..config import config

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (0.0, 1.0, 4.0)
REQUEST_TIMEOUT_SECONDS = 5.0


class WebhookDeliveryUnavailable(RuntimeError):
    pass


def _db_path() -> Path:
    return config.auth_db_path


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(str(_db_path()), timeout=30)
    except sqlite3.Error as exc:
        raise WebhookDeliveryUnavailable("Não foi possível abrir o registro de webhooks.") from exc
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except sqlite3.Error as exc:
        conn.rollback()
        raise WebhookDeliveryUnavailable("Não foi possível persistir a entrega de webhook.") from exc
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def migrate() -> None:
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_webhook_deliveries (
                delivery_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                url TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_status_code INTEGER,
                last_error TEXT,
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                UNIQUE(job_id, event_type)
            );
            CREATE INDEX IF NOT EXISTS idx_api_webhook_deliveries_status
                ON api_webhook_deliveries(status, created_at);
            """
        )


def _signature(secret: str, payload: bytes, timestamp: int) -> str:
    value = f"{timestamp}.".encode("ascii") + payload
    digest = hmac.new(secret.encode("utf-8"), value, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _safe_delivery_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for item in addresses:
        address = item[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _event_type(job: dict[str, Any]) -> str:
    if job.get("status") == "error":
        return "job.failed"
    if job.get("status") == "cancelled":
        return "job.cancelled"
    if str(job.get("tool") or "") == "api-clip":
        return "clip.ready"
    return "job.completed"


def _payload(job: dict[str, Any], event_type: str) -> dict[str, Any]:
    meta = job.get("meta") if isinstance(job.get("meta"), dict) else {}
    return {
        "id": str(job.get("job_id") or ""),
        "type": "clip" if str(meta.get("operation_type") or "") == "clip" else "transcription",
        "event": event_type,
        "status": "FAILED" if job.get("status") == "error" else "SUCCEEDED",
        "parent_job_id": job.get("parent_job_id") or meta.get("parent_job_id"),
        "created_at": job.get("created_at"),
        "finished_at": job.get("finished_at"),
        "format": job.get("api_output_format") or meta.get("output_format"),
        "language": job.get("api_language"),
        "duration_seconds": job.get("clip_duration_seconds") or job.get("estimated_audio_seconds"),
        "error_code": job.get("error_code") if job.get("status") == "error" else None,
    }


def notify_job(job: dict[str, Any]) -> dict[str, Any] | None:
    """Entrega no máximo uma vez por evento, com retry síncrono e sanitizado."""
    meta = job.get("meta") if isinstance(job.get("meta"), dict) else {}
    url = str(meta.get("webhook_url") or "").strip()
    secret = str(meta.get("webhook_secret") or "").strip()
    if not url or not secret or job.get("status") not in {"done", "error", "cancelled"}:
        return None
    if not _safe_delivery_url(url):
        return {"status": "failed", "attempts": 0, "error": "UNSAFE_WEBHOOK_URL"}
    event_type = _event_type(job)
    payload = _payload(job, event_type)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_hash = hashlib.sha256(raw).hexdigest()
    delivery_id = f"wh_{secrets.token_hex(12)}"
    try:
        with _conn() as conn:
            existing = conn.execute("SELECT delivery_id, status, attempts FROM api_webhook_deliveries WHERE job_id = ? AND event_type = ?", (str(job.get("job_id") or ""), event_type)).fetchone()
            if existing and existing["status"] == "delivered":
                return {"status": "delivered", "duplicate": True, "attempts": int(existing["attempts"])}
            if existing:
                delivery_id = str(existing["delivery_id"])
            else:
                conn.execute(
                    "INSERT INTO api_webhook_deliveries (delivery_id, job_id, event_type, url, payload_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (delivery_id, str(job.get("job_id") or ""), event_type, url, payload_hash, _now()),
                )
    except WebhookDeliveryUnavailable:
        raise

    last_error = None
    status_code = None
    opener = urllib.request.build_opener(_NoRedirect())
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            time.sleep(BACKOFF_SECONDS[attempt - 1])
        timestamp = int(time.time())
        request = urllib.request.Request(
            url,
            data=raw,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Viral-Webhook/1",
                "X-Viral-Event": event_type,
                "X-Viral-Delivery": delivery_id,
                "X-Viral-Signature": _signature(secret, raw, timestamp),
            },
        )
        try:
            with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                status_code = int(response.status)
                response.read(1024)
            if 200 <= status_code < 300:
                with _conn() as conn:
                    conn.execute("UPDATE api_webhook_deliveries SET status = 'delivered', attempts = ?, last_status_code = ?, last_error = NULL, delivered_at = ? WHERE delivery_id = ?", (attempt, status_code, _now(), delivery_id))
                return {"status": "delivered", "attempts": attempt, "status_code": status_code, "event": event_type}
            last_error = f"HTTP_{status_code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc.__class__.__name__

    with _conn() as conn:
        conn.execute("UPDATE api_webhook_deliveries SET status = 'failed', attempts = ?, last_status_code = ?, last_error = ? WHERE delivery_id = ?", (MAX_ATTEMPTS, status_code, last_error, delivery_id))
    return {"status": "failed", "attempts": MAX_ATTEMPTS, "status_code": status_code, "event": event_type}
