"""Registro central de jobs.

Toda ferramenta do ecossistema (YouTube, TikTok, Legendas, Voz, Canva) passa
por aqui. O objetivo é ter **um único padrão** de:

* ciclo de vida (`queued → running → done | error | cancelled`);
* rastro estruturado (`events`) + log legível (`log`);
* estágios nomeados (`stage`) com progresso;
* trilha de auditoria append-only em disco (`_jobs/_audit.log`), que sobrevive
  até mesmo à exclusão do job.
"""

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
_audit_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_cancel_events: dict[str, threading.Event] = {}
_futures: dict[str, Any] = {}
_executor = ThreadPoolExecutor(max_workers=config.max_workers)

TERMINAL_STATUSES = {"done", "error", "cancelled"}

TOOL_LABELS = {
    "youtube": "Desvio YouTube",
    "tiktok": "Clone TikTok",
    "legendar": "Legendas",
    "voice": "Voz V2V",
    "canva": "Limpeza Canva",
    "studio": "Estúdio de Vídeo IA",
    "clips": "Fábrica de Cortes",
}

MAX_EVENTS = 600
MAX_LOG_LINES = 600


class JobCancelled(RuntimeError):
    """Sinaliza que o operador cancelou o job de forma explícita."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tool_label(tool: str) -> str:
    return TOOL_LABELS.get(tool, tool or "desconhecido")


def _job_file(job_id: str) -> Path:
    return config.jobs_dir / f"{job_id}.json"


def _audit_file() -> Path:
    return config.jobs_dir / "_audit.log"


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _duration_ms(job: dict[str, Any]) -> int | None:
    start = _parse_iso(job.get("created_at"))
    if not start:
        return None
    end = _parse_iso(job.get("finished_at")) or datetime.now(timezone.utc)
    return max(0, int((end - start).total_seconds() * 1000))


def _normalize(job: dict[str, Any]) -> dict[str, Any]:
    """Garante que jobs antigos em disco tenham o mesmo formato dos novos."""
    job.setdefault("events", [])
    job.setdefault("log", [])
    job.setdefault("stage", None)
    job.setdefault("outputs", [])
    job.setdefault("artifacts", [])
    job.setdefault("meta", {})
    job.setdefault("progress", 0)
    job.setdefault("updated_at", job.get("finished_at") or job.get("created_at"))
    job["tool_label"] = tool_label(job.get("tool") or "")
    job["duration_ms"] = _duration_ms(job)
    job["terminal"] = job.get("status") in TERMINAL_STATUSES
    return job


# --- Trilha de auditoria append-only ----------------------------------------


def audit(action: str, job_id: str, tool: str = "", detail: str = "") -> None:
    """Grava uma linha imutável na trilha global (sobrevive ao delete do job)."""
    entry = {
        "ts": _now(),
        "action": action,
        "job_id": job_id,
        "tool": tool,
        "detail": detail,
    }
    try:
        config.jobs_dir.mkdir(parents=True, exist_ok=True)
        with _audit_lock:
            with _audit_file().open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        return


def read_audit(limit: int = 300, job_id: str | None = None) -> list[dict[str, Any]]:
    file = _audit_file()
    if not file.exists():
        return []
    try:
        lines = file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if job_id and entry.get("job_id") != job_id:
            continue
        entries.append(entry)
        if len(entries) >= limit:
            break
    return entries


# --- Ciclo de vida -----------------------------------------------------------


def create_job(tool: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    job_id = f"{tool}-{uuid.uuid4().hex[:12]}"
    now = _now()
    job = {
        "job_id": job_id,
        "tool": tool,
        "tool_label": tool_label(tool),
        "status": "queued",
        "stage": "criado",
        "message": "Job criado e enfileirado.",
        "progress": 0,
        "created_at": now,
        "updated_at": now,
        "finished_at": None,
        "duration_ms": 0,
        "terminal": False,
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
        "events": [],
        "meta": meta or {},
    }
    with _lock:
        _jobs[job_id] = job
        _cancel_events[job_id] = threading.Event()
    _event(job_id, "lifecycle", f"Job criado na ferramenta {tool_label(tool)}.", stage="criado")
    audit("created", job_id, tool, tool_label(tool))
    return get(job_id) or job


def _event(job_id: str, level: str, message: str, stage: str | None = None) -> None:
    """Registra um evento estruturado + a linha legível equivalente."""
    ts = _now()
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        current_stage = stage or job.get("stage") or "geral"
        entry = {"ts": ts, "level": level, "stage": current_stage, "message": message}
        events = list(job.get("events") or [])
        events.append(entry)
        job["events"] = events[-MAX_EVENTS:]
        clock = ts[11:19] if len(ts) >= 19 else ts
        lines = list(job.get("log") or [])
        lines.append(f"[{clock}] {level.upper():<9} {current_stage} · {message}")
        job["log"] = lines[-MAX_LOG_LINES:]
        job["updated_at"] = ts
    persist(job_id)


def log(job_id: str, line: str, level: str = "info", stage: str | None = None) -> None:
    """Log padrão de ferramenta (compatível com as chamadas existentes)."""
    _event(job_id, level, line, stage=stage)


def stage(
    job_id: str,
    name: str,
    message: str | None = None,
    progress: int | None = None,
) -> None:
    """Marca a entrada em um estágio nomeado — padrão para todas as ferramentas."""
    fields: dict[str, Any] = {"stage": name}
    if progress is not None:
        fields["progress"] = max(0, min(100, int(progress)))
    if message:
        fields["message"] = message
    update(job_id, **fields)
    _event(job_id, "stage", message or f"Etapa: {name}", stage=name)


def update(job_id: str, **fields: Any) -> None:
    previous_status = None
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        previous_status = job.get("status")
        job.update(fields)
        job["updated_at"] = _now()
        job["tool_label"] = tool_label(job.get("tool") or "")
        job["duration_ms"] = _duration_ms(job)
        job["terminal"] = job.get("status") in TERMINAL_STATUSES
        new_status = job.get("status")
        tool = job.get("tool") or ""
    persist(job_id)
    if new_status and new_status != previous_status:
        _event(job_id, "lifecycle", f"Status: {previous_status} → {new_status}.")
        audit("status", job_id, tool, f"{previous_status} → {new_status}")


def register_artifact(job_id: str, path: Path, kind: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        artifacts = list(job.get("artifacts") or [])
        entry = {"path": str(path), "kind": kind}
        duplicated = entry in artifacts
        if not duplicated:
            artifacts.append(entry)
        job["artifacts"] = artifacts

        job["updated_at"] = _now()
    persist(job_id)
    if not duplicated:
        _event(job_id, "artifact", f"Artefato {kind} registrado: {path.name}")


def cancel_event(job_id: str) -> threading.Event:
    with _lock:
        event = _cancel_events.get(job_id)
        if event is None:
            event = threading.Event()
            _cancel_events[job_id] = event
        return event


def is_cancelled(job_id: str) -> bool:
    return cancel_event(job_id).is_set()


def check_cancelled(job_id: str) -> None:
    """Ponto de checagem padrão para trabalhos longos."""
    if is_cancelled(job_id):
        raise JobCancelled(job_id)


def request_cancel(job_id: str) -> dict[str, Any] | None:
    job = get(job_id)
    if not job:
        return None

    cancel_event(job_id).set()
    if job.get("status") in TERMINAL_STATUSES:
        return job

    audit("cancel_requested", job_id, job.get("tool") or "")
    _event(job_id, "lifecycle", "Cancelamento solicitado pelo operador.", stage="cancelado")
    update(
        job_id,
        status="cancelled",
        stage="cancelado",
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
            return _normalize(dict(job))
    file = _job_file(job_id)
    if file.exists():
        try:
            return _normalize(json.loads(file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            return None
    return None


def list_jobs(limit: int = 200) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    try:
        files = sorted(
            config.jobs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )
    except OSError:
        files = []
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or not data.get("job_id"):
            continue
        seen[data["job_id"]] = _normalize(data)
        if len(seen) >= limit:
            break
    with _lock:
        for job_id, job in _jobs.items():
            seen[job_id] = _normalize(dict(job))
    return sorted(seen.values(), key=lambda j: j.get("created_at") or "", reverse=True)[:limit]


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Estatísticas padronizadas usadas pela Central de Jobs."""
    by_tool: dict[str, dict[str, int]] = {}
    for job in items:
        tool = job.get("tool") or "desconhecido"
        bucket = by_tool.setdefault(
            tool,
            {"total": 0, "done": 0, "error": 0, "cancelled": 0, "running": 0, "bytes": 0},
        )
        bucket["total"] += 1
        status = job.get("status")
        if status in {"running", "queued"}:
            bucket["running"] += 1
        elif status in bucket:
            bucket[status] += 1
        bucket["bytes"] += int(job.get("size_bytes") or 0)
    return {
        "total": len(items),
        "done": sum(1 for j in items if j.get("status") == "done"),
        "error": sum(1 for j in items if j.get("status") == "error"),
        "cancelled": sum(1 for j in items if j.get("status") == "cancelled"),
        "running": sum(1 for j in items if j.get("status") in {"running", "queued"}),
        "bytes": sum(int(j.get("size_bytes") or 0) for j in items),
        "by_tool": by_tool,
    }


def persist(job_id: str) -> None:
    job = None
    with _lock:
        if job_id in _jobs:
            job = _normalize(dict(_jobs[job_id]))
    if job is None:
        return
    try:
        config.jobs_dir.mkdir(parents=True, exist_ok=True)
        _job_file(job_id).write_text(
            json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        return


def submit(job_id: str, work: Callable[[str], None]) -> None:
    """Executa o trabalho pesado fora do request, capturando qualquer falha."""

    def runner() -> None:
        if is_cancelled(job_id):
            update(
                job_id,
                status="cancelled",
                stage="cancelado",
                message="Job cancelado antes de iniciar.",
                finished_at=_now(),
            )
            return
        update(job_id, status="running", stage="processando", message="Processando…")
        try:
            work(job_id)
            job = get(job_id) or {}
            if job.get("status") not in TERMINAL_STATUSES:
                update(
                    job_id,
                    status="done",
                    stage="concluido",
                    message="Concluído.",
                    progress=100,
                    finished_at=_now(),
                )
            elif job.get("status") == "done" and not job.get("finished_at"):
                update(job_id, finished_at=_now())
        except JobCancelled:
            update(
                job_id,
                status="cancelled",
                stage="cancelado",
                message="Job cancelado pelo operador.",
                finished_at=_now(),
            )
        except Exception as exc:  # noqa: BLE001 - toda falha vira status de job
            _event(job_id, "error", f"ERRO: {exc}", stage="falha")
            update(
                job_id,
                status="error",
                stage="falha",
                message=str(exc),
                finished_at=_now(),
            )
        finally:
            with _lock:
                _futures.pop(job_id, None)

    audit("queued", job_id, (get(job_id) or {}).get("tool") or "")
    future = _executor.submit(runner)
    with _lock:
        _futures[job_id] = future


def fail(job_id: str, message: str) -> None:
    """Marca falha de validação antes do job entrar na fila."""
    _event(job_id, "error", message, stage="falha")
    update(job_id, status="error", stage="falha", message=message, finished_at=_now())


def delete(job_id: str) -> None:
    """Remove o job do registro em memória, o JSON e os arquivos gerados."""
    request_cancel(job_id)
    wait(job_id, timeout=10.0)
    job = get(job_id)
    audit(
        "deleted",
        job_id,
        (job or {}).get("tool") or "",
        f"status={(job or {}).get('status')} arquivo={(job or {}).get('filename')}",
    )
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
