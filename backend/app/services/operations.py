"""Representação pública uniforme de operações longas da Mago API.

O engine interno continua usando jobs por compatibilidade com o painel. Este
adapter cria uma fronteira estável para consumidores externos sem expor PID,
host, paths locais, provider ou mensagens brutas de exceção.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from flask import url_for

from .api_errors import operation_error


TERMINAL_INTERNAL = {"done", "error", "cancelled"}
TERMINAL_PUBLIC = {"SUCCEEDED", "FAILED", "CANCELLED", "EXPIRED"}


def operation_name(job_id: str) -> str:
    """Gera um nome estável e opaco o suficiente para a superfície HTTP."""
    return f"operations/{job_id}"


def _expired(job: dict[str, Any]) -> bool:
    if job.get("status") != "done":
        return False
    value = job.get("expires_at")
    if not isinstance(value, str) or not value:
        return False
    try:
        expires = datetime.fromisoformat(value)
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires <= datetime.now(timezone.utc)


def public_state(job: dict[str, Any]) -> str:
    """Converte estados internos para o enum pequeno e documentado da API."""
    if _expired(job):
        return "EXPIRED"
    return {
        "queued": "PENDING",
        "running": "RUNNING",
        "done": "SUCCEEDED",
        "error": "FAILED",
        "cancelled": "CANCELLED",
    }.get(str(job.get("status") or ""), "PENDING")


def _progress(job: dict[str, Any], state: str) -> int:
    if state == "SUCCEEDED":
        return 100
    try:
        return max(0, min(100, int(job.get("progress") or 0)))
    except (TypeError, ValueError):
        return 0


def _metadata(job: dict[str, Any], state: str) -> dict[str, Any]:
    """Metadata segura, sem dados internos de infraestrutura."""
    metadata: dict[str, Any] = {
        "progress": _progress(job, state),
        "stage": job.get("stage"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "expires_at": job.get("expires_at"),
    }
    attempt = job.get("attempt")
    if isinstance(attempt, int) and attempt > 0:
        metadata["attempt"] = attempt
    return {key: value for key, value in metadata.items() if value is not None}


def _response(job: dict[str, Any], *, result_url: str | None) -> dict[str, Any] | None:
    if public_state(job) != "SUCCEEDED" or not result_url:
        return None
    return {
        "job_id": str(job.get("job_id") or ""),
        "format": job.get("api_output_format") or job.get("meta", {}).get("output_format"),
        "language": job.get("api_language"),
        "result_url": result_url,
    }


def _error(job: dict[str, Any], state: str) -> dict[str, Any] | None:
    if state == "FAILED":
        return operation_error(
            str(job.get("error_code") or "JOB_FAILED"),
            "O processamento da transcrição falhou. Consulte os eventos da operação.",
            retryable=bool(job.get("retryable")),
        )
    if state == "CANCELLED":
        return operation_error(
            "CANCELLED",
            "A operação foi cancelada.",
            retryable=False,
        )
    if state == "EXPIRED":
        return operation_error(
            "RESULT_EXPIRED",
            "O resultado desta operação expirou.",
            retryable=False,
        )
    return None


def operation_view(
    job: dict[str, Any],
    *,
    result_url: str | None = None,
) -> dict[str, Any]:
    """Converte um job interno em uma operação pública sanitizada.

    O recurso oferece os campos canônicos de operação longa e mantém campos
    legados aditivos para consumidores do primeiro contrato.
    """
    job_id = str(job.get("job_id") or "")
    state = public_state(job)
    name = operation_name(job_id)
    poll_url = url_for("api_v1.get_operation", job_id=job_id, _external=True)
    payload: dict[str, Any] = {
        "name": name,
        "id": job_id,
        "object": "operation",
        "type": "transcription",
        "done": state in TERMINAL_PUBLIC,
        "status": state,
        "metadata": _metadata(job, state),
        "response": _response(job, result_url=result_url),
        "error": _error(job, state),
        "poll_url": poll_url,
        "api_version": "v1",
    }
    # Estes campos continuam disponíveis na v1 para não quebrar consumidores;
    # os campos canônicos acima são a fonte de evolução.
    payload.update(
        {
            "progress": _progress(job, state),
            "stage": job.get("stage"),
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "expires_at": job.get("expires_at"),
            "result_url": payload["response"].get("result_url")
            if payload["response"]
            else None,
            "error": payload["error"],
        }
    )
    return payload


def job_id_from_operation_name(value: str) -> str | None:
    prefix = "operations/"
    if not value.startswith(prefix):
        return None
    job_id = value[len(prefix) :]
    if not job_id or "/" in job_id:
        return None
    return job_id
