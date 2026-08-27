"""Worker persistente do data plane da Mago API.

O processo não recebe requests. Ele reivindica intenções gravadas em
``api_queue``, executa o tipo conhecido e devolve o estado para o JSON de job.
"""

from __future__ import annotations

import os
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Any

from app import create_app
from app.config import config
from app.services import jobs, persistent_queue, rate_limits, transcribe
from app.services.api_errors import operation_error

_STOP = threading.Event()
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _release_active_slot(job_id: str) -> None:
    job = jobs.get(job_id) or {}
    meta = job.get("meta") or {}
    consumer_id = meta.get("api_key_id") or meta.get("consumer_id")
    if not consumer_id:
        return
    try:
        rate_limits.release_active_job(str(consumer_id), job_id=job_id)
    except rate_limits.UsageUnavailable:
        return


LEASE_SECONDS = max(60, int(os.environ.get("API_QUEUE_LEASE_SECONDS", "900")))
POLL_SECONDS = max(1, float(os.environ.get("API_QUEUE_POLL_SECONDS", "2")))


def _signal(_signum: int, _frame: Any) -> None:
    _STOP.set()


def _retryable(exc: Exception) -> tuple[str, bool]:
    message = str(exc).lower()
    if isinstance(exc, transcribe.TranscribeError):
        if any(marker in message for marker in ("401", "403", "400", "422", "invalid", "recusada")):
            return "PROVIDER_AUTH_FAILED", False
        if "429" in message or "limite" in message:
            return "PROVIDER_RATE_LIMITED", True
        if "quota" in message or "402" in message or "créditos" in message:
            return "PROVIDER_QUOTA_EXCEEDED", False
        if "rede" in message or "tempo esgotado" in message or "timeout" in message:
            return "PROVIDER_UNAVAILABLE", True
        return "PROVIDER_ERROR", False
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return "WORKER_IO_ERROR", True
    return "WORKER_ERROR", False


def _public_message(code: str) -> str:
    messages = {
        "PROVIDER_AUTH_FAILED": "O provider de transcrição recusou a credencial configurada.",
        "PROVIDER_RATE_LIMITED": "O provider de transcrição atingiu o limite temporário.",
        "PROVIDER_QUOTA_EXCEEDED": "A quota do provider de transcrição foi atingida.",
        "PROVIDER_UNAVAILABLE": "O provider de transcrição está temporariamente indisponível.",
        "PROVIDER_ERROR": "O provider de transcrição não concluiu a operação.",
        "WORKER_IO_ERROR": "O worker não conseguiu ler ou gravar a mídia.",
        "WORKER_ERROR": "O worker não conseguiu concluir a operação.",
    }
    return messages.get(code, "A operação não foi concluída.")


def _heartbeat_loop(job_id: str, stop_event: threading.Event) -> None:
    while not _STOP.is_set() and not stop_event.is_set():
        stop_event.wait(min(30, max(10, LEASE_SECONDS // 3)))
        if _STOP.is_set() or stop_event.is_set():
            return
        try:
            persistent_queue.heartbeat(job_id, WORKER_ID, lease_seconds=LEASE_SECONDS)
            jobs.update(job_id, heartbeat_at=jobs._now(), owner_pid=os.getpid(), owner_host=socket.gethostname())
        except Exception:
            return


def _run_api_transcription(item: dict[str, Any]) -> None:
    job_id = str(item["job_id"])
    payload = item.get("payload") or {}
    source = Path(str(payload.get("source_path") or ""))
    output_format = str(payload.get("output_format") or "srt")
    language = str(payload.get("language") or "")
    if not source.is_file():
        raise FileNotFoundError("source media is missing")

    from app.blueprints.api_v1 import _run_transcription

    stop_event = threading.Event()
    beat = threading.Thread(target=_heartbeat_loop, args=(job_id, stop_event), daemon=True)
    beat.start()
    try:
        jobs.load(job_id)
        _run_transcription(job_id, source, output_format, language, cleanup_source=False)
    finally:
        stop_event.set()
        beat.join(timeout=1)


def _dispatch(item: dict[str, Any]) -> None:
    if item.get("kind") == "api-transcription":
        _run_api_transcription(item)
        return
    raise ValueError("unsupported queue kind")


def _process(item: dict[str, Any]) -> None:
    job_id = str(item["job_id"])
    attempts = int(item.get("attempts") or 1)
    source = Path(str((item.get("payload") or {}).get("source_path") or ""))
    try:
        jobs.load(job_id)
        if jobs.is_cancelled(job_id):
            jobs.update(job_id, status="cancelled", stage="cancelado", message="Job cancelado antes de iniciar.", finished_at=jobs._now())
            persistent_queue.complete(job_id, WORKER_ID)
            _release_active_slot(job_id)
            source.unlink(missing_ok=True)
            return
        jobs.update(
            job_id,
            status="running",
            stage="processando",
            message="Processando em worker persistente.",
            owner_pid=os.getpid(),
            owner_host=socket.gethostname(),
            heartbeat_at=jobs._now(),
            attempt=attempts,
        )
        _dispatch(item)
        job = jobs.get(job_id) or {}
        if job.get("status") not in jobs.TERMINAL_STATUSES:
            jobs.update(job_id, status="done", stage="concluido", message="Concluído.", progress=100, finished_at=jobs._now())
        persistent_queue.complete(job_id, WORKER_ID)
        _release_active_slot(job_id)
        source.unlink(missing_ok=True)
    except jobs.JobCancelled:
        jobs.update(job_id, status="cancelled", stage="cancelado", message="Job cancelado pelo operador.", finished_at=jobs._now())
        persistent_queue.complete(job_id, WORKER_ID)
        _release_active_slot(job_id)
        source.unlink(missing_ok=True)
    except Exception as exc:
        code, retryable = _retryable(exc)
        terminal = persistent_queue.fail(job_id, code, retryable=retryable, worker_id=WORKER_ID)
        if terminal:
            jobs.update(
                job_id,
                status="error",
                stage="falha",
                message=_public_message(code),
                error_code=code,
                retryable=False,
                finished_at=jobs._now(),
            )
            _release_active_slot(job_id)
            source.unlink(missing_ok=True)
        else:
            jobs.update(job_id, status="queued", stage="aguardando_retry", message="Falha temporária; retry agendado.", error_code=code, retryable=True)


def main() -> int:
    signal.signal(signal.SIGTERM, _signal)
    signal.signal(signal.SIGINT, _signal)
    app = create_app()
    persistent_queue.check_ready()
    jobs.reconcile_orphans()
    with app.app_context():
        while not _STOP.is_set():
            try:
                item = persistent_queue.claim(WORKER_ID, lease_seconds=LEASE_SECONDS)
            except persistent_queue.QueueUnavailable:
                time.sleep(POLL_SECONDS)
                continue
            if not item:
                time.sleep(POLL_SECONDS)
                continue
            _process(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
