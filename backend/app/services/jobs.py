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
import os
import queue
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import shutil

from ..config import config

_lock = threading.Lock()
_audit_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_cancel_events: dict[str, threading.Event] = {}
_done_events: dict[str, threading.Event] = {}

# --- Execução de jobs longos -------------------------------------------------
# Não usamos ThreadPoolExecutor: ele registra um hook de `atexit` que tenta
# agendar/join threads durante o shutdown do interpretador. Em jobs longos de
# voz/dublagem isso produzia justamente o erro
# `cannot schedule new futures after interpreter shutdown` quando o Gunicorn
# reciclava o worker no meio do processamento. Aqui a fila é nossa e as threads
# são daemon: o shutdown nunca fica preso nem tenta agendar trabalho novo.
_queue: "queue.Queue[tuple[str, Callable[[str], None]]]" = queue.Queue()
_pool_lock = threading.Lock()
_pool_started = False
_shutting_down = threading.Event()

_PID = os.getpid()
try:
    _HOST = socket.gethostname()
except OSError:  # pragma: no cover
    _HOST = "desconhecido"

# Batimento do job em disco. Se o processo morrer (deploy, restart, crash,
# reciclagem do Gunicorn), o batimento para e o job é declarado interrompido
# em vez de ficar "processando" para sempre na Central de Jobs.
HEARTBEAT_SECONDS = int(os.environ.get("VIRAL_JOB_HEARTBEAT", "15"))
STALE_AFTER_SECONDS = int(os.environ.get("VIRAL_JOB_STALE_SECONDS", "180"))
INTERRUPTED_MESSAGE = (
    "Job interrompido: o processo que executava a tarefa foi encerrado "
    "(deploy, restart ou reciclagem do worker). Reenvie o job."
)

TERMINAL_STATUSES = {"done", "error", "cancelled"}


TOOL_LABELS = {
    "youtube": "Desvio YouTube",
    "tiktok": "Clone TikTok",
    "legendar": "Legendas",
    "transcribe": "Transcrição",
    "voice": "Voz V2V",
    "canva": "Limpeza Canva",
    "studio": "Estúdio de Vídeo IA",
    "recap": "Recap Narrado",
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


def _cancel_file(job_id: str) -> Path:
    """Sinal de cancelamento em disco — funciona entre workers do Gunicorn."""
    return config.jobs_dir / f"{job_id}.cancel"


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
    job.setdefault("heartbeat_at", None)
    job.setdefault("owner_pid", None)
    job.setdefault("owner_host", None)
    job["tool_label"] = tool_label(job.get("tool") or "")
    job["duration_ms"] = _duration_ms(job)
    job["terminal"] = job.get("status") in TERMINAL_STATUSES
    return job


# --- Detecção de job órfão (processo morreu no meio) -------------------------


def _pid_alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
    except (TypeError, ValueError):
        return False
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _is_orphan(job: dict[str, Any]) -> bool:
    """Job não-terminal cujo processo dono não bate mais o coração."""
    if job.get("status") in TERMINAL_STATUSES:
        return False
    owner_pid = job.get("owner_pid")
    owner_host = job.get("owner_host")
    if owner_host == _HOST and owner_pid == _PID:
        return False  # é nosso: está vivo por definição
    if owner_host == _HOST and owner_pid and _pid_alive(owner_pid):
        return False  # outro worker do Gunicorn, ainda vivo
    beat = _parse_iso(job.get("heartbeat_at")) or _parse_iso(job.get("updated_at"))
    if not beat:
        beat = _parse_iso(job.get("created_at"))
    if not beat:
        return False
    age = (datetime.now(timezone.utc) - beat).total_seconds()
    return age > STALE_AFTER_SECONDS


def _write_job_file(job: dict[str, Any]) -> None:
    try:
        config.jobs_dir.mkdir(parents=True, exist_ok=True)
        _job_file(job["job_id"]).write_text(
            json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except (OSError, KeyError):
        return


def _heal(job: dict[str, Any]) -> dict[str, Any]:
    """Converte job órfão em falha explícita — nunca deixa 'processando' eterno."""
    if not _is_orphan(job):
        return job
    job["status"] = "error"
    job["stage"] = "interrompido"
    job["message"] = INTERRUPTED_MESSAGE
    job["finished_at"] = job.get("finished_at") or _now()
    job["updated_at"] = _now()
    job["terminal"] = True
    events = list(job.get("events") or [])
    events.append(
        {"ts": _now(), "level": "error", "stage": "interrompido", "message": INTERRUPTED_MESSAGE}
    )
    job["events"] = events[-MAX_EVENTS:]
    lines = list(job.get("log") or [])
    lines.append(f"[{_now()[11:19]}] ERROR     interrompido · {INTERRUPTED_MESSAGE}")
    job["log"] = lines[-MAX_LOG_LINES:]
    _write_job_file(job)
    with _lock:
        _jobs.pop(job["job_id"], None)
    audit("interrupted", job.get("job_id") or "", job.get("tool") or "", "processo dono encerrado")
    return job


def reconcile_orphans() -> int:
    """Roda no boot: fecha jobs que ficaram presos em `running` após restart."""
    healed = 0
    try:
        files = list(config.jobs_dir.glob("*.json"))
    except OSError:
        return 0
    for file in files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict) or not data.get("job_id"):
            continue
        data = _normalize(data)
        if data.get("status") in TERMINAL_STATUSES:
            continue
        # No boot, qualquer job não-terminal sem dono vivo é órfão — mesmo recente.
        owner_pid = data.get("owner_pid")
        if data.get("owner_host") == _HOST and owner_pid and _pid_alive(owner_pid):
            continue
        data["heartbeat_at"] = data.get("heartbeat_at") or data.get("updated_at")
        data["owner_pid"] = None
        data["owner_host"] = None
        data["status"] = "error"
        data["stage"] = "interrompido"
        data["message"] = INTERRUPTED_MESSAGE
        data["finished_at"] = data.get("finished_at") or _now()
        data["updated_at"] = _now()
        data["terminal"] = True
        _write_job_file(data)
        audit("interrupted", data["job_id"], data.get("tool") or "", "reconciliação de boot")
        healed += 1
    return healed



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
    # Log é gravado com throttle: status/progresso usam `update()`, que grava na hora.
    persist(job_id, throttle=level == "info")



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


_cancel_cache: dict[str, tuple[float, bool]] = {}
_CANCEL_TTL = 1.0


def is_cancelled(job_id: str) -> bool:
    """Vale para o processo atual **e** para cancelamentos vindos de outro worker."""
    if cancel_event(job_id).is_set():
        return True
    now = time.monotonic()
    cached = _cancel_cache.get(job_id)
    if cached and now - cached[0] < _CANCEL_TTL:
        return cached[1]
    try:
        flagged = _cancel_file(job_id).exists()
    except OSError:
        flagged = False
    _cancel_cache[job_id] = (now, flagged)
    if flagged:
        cancel_event(job_id).set()
    return flagged


def check_cancelled(job_id: str) -> None:
    """Ponto de checagem padrão para trabalhos longos."""
    if is_cancelled(job_id):
        raise JobCancelled(job_id)


def request_cancel(job_id: str) -> dict[str, Any] | None:
    job = get(job_id)
    if not job:
        return None

    cancel_event(job_id).set()
    _cancel_cache[job_id] = (time.monotonic(), True)
    try:
        config.jobs_dir.mkdir(parents=True, exist_ok=True)
        _cancel_file(job_id).write_text(_now(), encoding="utf-8")
    except OSError:
        pass
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


def _done_event(job_id: str) -> threading.Event:
    with _lock:
        event = _done_events.get(job_id)
        if event is None:
            event = threading.Event()
            _done_events[job_id] = event
        return event


def wait(job_id: str, timeout: float = 8.0) -> None:
    with _lock:
        event = _done_events.get(job_id)
    if event is None:
        return
    event.wait(timeout=timeout)


def get(job_id: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            return _heal(_normalize(dict(job)))
    file = _job_file(job_id)
    if file.exists():
        try:
            return _heal(_normalize(json.loads(file.read_text(encoding="utf-8"))))
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
        seen[data["job_id"]] = _heal(_normalize(data))
        if len(seen) >= limit:
            break
    with _lock:
        snapshot = {job_id: dict(job) for job_id, job in _jobs.items()}
    for job_id, job in snapshot.items():
        seen[job_id] = _heal(_normalize(job))
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


_last_persist: dict[str, float] = {}
PERSIST_THROTTLE_SECONDS = 1.0


def persist(job_id: str, *, throttle: bool = False) -> None:
    """Grava o job em disco. Com `throttle`, no máximo 1x por segundo.

    O FFmpeg cospe centenas de linhas por minuto; gravar o JSON inteiro a cada
    linha transforma um job longo em I/O puro. Mudanças de status/progresso
    continuam gravando na hora.
    """
    if throttle:
        now = time.monotonic()
        last = _last_persist.get(job_id, 0.0)
        if now - last < PERSIST_THROTTLE_SECONDS:
            return
        _last_persist[job_id] = now
    else:
        _last_persist[job_id] = time.monotonic()
    job = None
    with _lock:
        if job_id in _jobs:
            job = _normalize(dict(_jobs[job_id]))
    if job is None:
        return
    try:
        config.jobs_dir.mkdir(parents=True, exist_ok=True)
        tmp = _job_file(job_id).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_job_file(job_id))
    except OSError:
        return



# --- Pool próprio de execução ------------------------------------------------


def _touch_heartbeat(job_id: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job.get("status") in TERMINAL_STATUSES:
            return
        job["heartbeat_at"] = _now()
        job["owner_pid"] = _PID
        job["owner_host"] = _HOST
    persist(job_id)


def _heartbeat_loop() -> None:
    """Prova de vida periódica: sem ela, o job é declarado interrompido."""
    while not _shutting_down.is_set():
        _shutting_down.wait(HEARTBEAT_SECONDS)
        with _lock:
            active = [
                jid
                for jid, job in _jobs.items()
                if job.get("status") in {"running", "queued"} and job.get("owner_pid") == _PID
            ]
        for job_id in active:
            _touch_heartbeat(job_id)


def _run_job(job_id: str, work: Callable[[str], None]) -> None:
    done = _done_event(job_id)
    try:
        if is_cancelled(job_id):
            update(
                job_id,
                status="cancelled",
                stage="cancelado",
                message="Job cancelado antes de iniciar.",
                finished_at=_now(),
            )
            return
        update(
            job_id,
            status="running",
            stage="processando",
            message="Processando…",
            owner_pid=_PID,
            owner_host=_HOST,
            heartbeat_at=_now(),
        )
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
        except BaseException as exc:  # noqa: BLE001 - toda falha vira status de job
            # BaseException cobre SystemExit/KeyboardInterrupt disparados quando o
            # worker do Gunicorn é encerrado no meio do processamento.
            _event(job_id, "error", f"ERRO: {exc}", stage="falha")
            update(
                job_id,
                status="error",
                stage="falha",
                message=str(exc) or exc.__class__.__name__,
                finished_at=_now(),
            )
    finally:
        done.set()


def _worker_loop() -> None:
    while True:
        try:
            item = _queue.get(timeout=1.0)
        except queue.Empty:
            if _shutting_down.is_set():
                return
            continue
        job_id, work = item
        try:
            _run_job(job_id, work)
        finally:
            _queue.task_done()


def _ensure_pool() -> None:
    global _pool_started
    with _pool_lock:
        if _pool_started:
            return
        for index in range(max(1, config.max_workers)):
            threading.Thread(
                target=_worker_loop, name=f"viral-job-{index}", daemon=True
            ).start()
        threading.Thread(target=_heartbeat_loop, name="viral-job-heartbeat", daemon=True).start()
        _pool_started = True


def shutdown(_signum: Any = None, _frame: Any = None) -> None:
    """Encerramento limpo: para o batimento e não aceita trabalho novo."""
    _shutting_down.set()


def queue_depth() -> int:
    return _queue.qsize()


def submit(job_id: str, work: Callable[[str], None]) -> None:
    """Executa o trabalho pesado fora do request, capturando qualquer falha."""
    _ensure_pool()
    _done_event(job_id).clear()
    audit("queued", job_id, (get(job_id) or {}).get("tool") or "")
    _touch_heartbeat(job_id)
    _queue.put((job_id, work))



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
        _done_events.pop(job_id, None)
    _cancel_cache.pop(job_id, None)
    paths: list[Path] = [_job_file(job_id), _cancel_file(job_id)]

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
