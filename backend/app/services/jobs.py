"""Registro de jobs: estado em memória + persistência em JSON no disco."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import shutil

from ..config import config

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_cancel_events: dict[str, threading.Event] = {}
_futures: dict[str, Any] = {}
_executor = ThreadPoolExecutor(max_workers=config.max_workers)


class JobCancelled(RuntimeError):
    """Sinaliza que o operador cancelou o job de forma explícita."""


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
        "size_bytes": 0,
        "md5_before": None,
        "md5_after": None,
        "sha256_after": None,
        "sterilization": None,
        "outputs": [],
        "artifacts": [],
        "source_kind": None,
        "source_label": None,
        "source_path": None,
        "source_url": None,
        "log": [],
        "meta": meta or {},
    }
    with _lock:
        _jobs[job_id] = job
        _cancel_events[job_id] = threading.Event()
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


def register_artifact(job_id: str, path: Path, kind: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        artifacts = list(job.get("artifacts") or [])
        entry = {"path": str(path), "kind": kind}
        if entry not in artifacts:
            artifacts.append(entry)
        job["artifacts"] = artifacts
    persist(job_id)


def cancel_event(job_id: str) -> threading.Event:
    with _lock:
        event = _cancel_events.get(job_id)
        if event is None:
            event = threading.Event()
            _cancel_events[job_id] = event
        return event


def is_cancelled(job_id: str) -> bool:
    return cancel_event(job_id).is_set()


def request_cancel(job_id: str) -> dict[str, Any] | None:
    job = get(job_id)
    if not job:
        return None

    cancel_event(job_id).set()
    if job.get("status") in {"done", "error", "cancelled"}:
        return job

    update(
        job_id,
        status="cancelled",
        message="Job cancelado pelo operador.",
        finished_at=_now(),
    )
    return get(job_id)


def wait(job_id: str, timeout: float = 8.0) -> None:
    future = None
    with _lock:
        future = _futures.get(job_id)
    if future is None:
        return
    try:
        future.result(timeout=timeout)
    except Exception:  # noqa: BLE001
        return


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
        if is_cancelled(job_id):
            update(
                job_id,
                status="cancelled",
                message="Job cancelado antes de iniciar.",
                finished_at=_now(),
            )
            return
        update(job_id, status="running", message="Processando…")
        try:
            work(job_id)
            job = get(job_id) or {}
            if job.get("status") not in {"error", "done", "cancelled"}:
                update(job_id, status="done", message="Concluído.", progress=100, finished_at=_now())
        except JobCancelled:
            update(job_id, status="cancelled", message="Job cancelado pelo operador.", finished_at=_now())
        except Exception as exc:  # noqa: BLE001 - toda falha vira status de job
            log(job_id, f"ERRO: {exc}")
            update(job_id, status="error", message=str(exc), finished_at=_now())
        finally:
            with _lock:
                _futures.pop(job_id, None)

    future = _executor.submit(runner)
    with _lock:
        _futures[job_id] = future


def delete(job_id: str) -> None:
    """Remove o job do registro em memória, o JSON e os arquivos gerados."""
    request_cancel(job_id)
    wait(job_id, timeout=10.0)
    job = get(job_id)
    with _lock:
        _jobs.pop(job_id, None)
        _cancel_events.pop(job_id, None)
        _futures.pop(job_id, None)
    paths: list[Path] = [_job_file(job_id)]
    if job:
        for raw in job.get("artifacts") or []:
            if isinstance(raw, str) and raw:
                paths.append(Path(raw))
            elif isinstance(raw, dict):
                path = raw.get("path")
                if isinstance(path, str) and path:
                    paths.append(Path(path))
        tool = job.get("tool") or ""
        folder = config.tool_dir(tool) / job_id
        paths.append(folder)

    # Remove qualquer rastro no storage, mesmo quando o job morreu no meio.
    try:
        for match in config.storage_dir.rglob(f"{job_id}*"):
            paths.append(match)
    except OSError:
        pass

    seen: set[str] = set()
    ordered: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)

    for path in sorted(ordered, key=lambda p: len(p.parts), reverse=True):
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except OSError:
            continue
