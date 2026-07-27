"""Registro de jobs: estado em memória + persistência em JSON no disco."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..config import config

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_executor = ThreadPoolExecutor(max_workers=config.max_workers)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _job_file(job_id: str) -> Path:
    return config.jobs_dir / f"{job_id}.json"


def create_job(tool: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    job_id = f"{tool}-{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id,
        "tool": tool,
        "status": "queued",
        "message": "Job criado e enfileirado.",
        "progress": 0,
        "created_at": _now(),
        "finished_at": None,
        "download_url": None,
        "filename": None,
        "md5_before": None,
        "md5_after": None,
        "log": [],
        "meta": meta or {},
    }
    with _lock:
        _jobs[job_id] = job
    persist(job_id)
    return job


def update(job_id: str, **fields: Any) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.update(fields)
    persist(job_id)


def log(job_id: str, line: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job["log"].append(line)
        job["log"] = job["log"][-400:]
    persist(job_id)


def get(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            return dict(job)
    file = _job_file(job_id)
    if file.exists():
        try:
            return json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def list_jobs(limit: int = 200) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for file in sorted(config.jobs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        seen[data["job_id"]] = data
        if len(seen) >= limit:
            break
    with _lock:
        for job_id, job in _jobs.items():
            seen[job_id] = dict(job)
    return sorted(seen.values(), key=lambda j: j.get("created_at") or "", reverse=True)[:limit]


def persist(job_id: str) -> None:
    job = None
    with _lock:
        if job_id in _jobs:
            job = dict(_jobs[job_id])
    if job is None:
        return
    config.jobs_dir.mkdir(parents=True, exist_ok=True)
    _job_file(job_id).write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def submit(job_id: str, work: Callable[[str], None]) -> None:
    """Executa o trabalho pesado fora do request, capturando qualquer falha."""

    def runner() -> None:
        update(job_id, status="running", message="Processando…")
        try:
            work(job_id)
            job = get(job_id) or {}
            if job.get("status") not in {"error", "done"}:
                update(job_id, status="done", message="Concluído.", progress=100, finished_at=_now())
        except Exception as exc:  # noqa: BLE001 - toda falha vira status de job
            log(job_id, f"ERRO: {exc}")
            update(job_id, status="error", message=str(exc), finished_at=_now())

    _executor.submit(runner)
