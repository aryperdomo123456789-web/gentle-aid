"""Retenção e garbage collection de artefatos de API.

Jobs permanecem como envelope histórico. Arquivos físicos e reservas de storage
são removidos quando o TTL vence; eventos de uso não são apagados.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import config
from . import jobs


def retention_days() -> int:
    try:
        return max(1, int(__import__("os").environ.get("API_RETENTION_DAYS", "7")))
    except (TypeError, ValueError):
        return 7


def expiry_from_now() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=retention_days())).isoformat(timespec="seconds")


def _parse(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _expired(job: dict[str, Any], now: datetime) -> bool:
    if str(job.get("retention_status") or "") == "expired":
        return False
    if job.get("status") not in {"done", "error", "cancelled"}:
        return False
    expires = _parse(job.get("expires_at"))
    return bool(expires and expires <= now)


def _safe_paths(job: dict[str, Any]) -> list[Path]:
    root = config.storage_dir.resolve()
    paths: list[Path] = []
    values = [job.get("source_path"), job.get("download_path"), job.get("output_path")]
    for item in job.get("artifacts") or []:
        if isinstance(item, dict):
            values.append(item.get("path"))
        elif isinstance(item, str):
            values.append(item)
    for raw in values:
        if not isinstance(raw, str) or not raw:
            continue
        try:
            candidate = Path(raw).resolve()
            if candidate.is_relative_to(root):
                paths.append(candidate)
        except (OSError, RuntimeError, ValueError):
            continue
    return list(dict.fromkeys(paths))


def _mark_expired(job: dict[str, Any]) -> int:
    job_id = str(job.get("job_id") or "")
    if not job_id:
        return 0
    paths = _safe_paths(job)
    removed = 0
    artifacts = []
    for item in job.get("artifacts") or []:
        if isinstance(item, dict):
            copy = dict(item)
            copy["state"] = "expired"
            copy["expired_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            artifacts.append(copy)
    for path in paths:
        try:
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    meta = job.get("meta") if isinstance(job.get("meta"), dict) else {}
    consumer_id = meta.get("api_key_id") or meta.get("consumer_id")
    if consumer_id:
        try:
            from . import billing
            billing.release_storage(billing.account_id_for_consumer(str(consumer_id)), resource_id=job_id)
        except Exception:
            pass
    jobs.update(job_id, artifacts=artifacts, retention_status="expired", expired_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), download_url=None, source_path=None)
    jobs.audit("retention_expired", job_id, str(job.get("tool") or ""), f"artefatos_removidos={removed}")
    return removed


def collect(*, limit: int = 200, dry_run: bool = False) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    scanned = 0
    expired = 0
    removed = 0
    try:
        files = list(config.jobs_dir.glob("*.json"))
    except OSError:
        files = []
    for file in files:
        if scanned >= max(1, int(limit)):
            break
        try:
            job = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(job, dict) or not job.get("job_id"):
            continue
        scanned += 1
        if not _expired(job, now):
            continue
        expired += 1
        if not dry_run:
            removed += _mark_expired(job)
    return {"scanned": scanned, "expired": expired, "files_removed": removed, "dry_run": bool(dry_run)}
