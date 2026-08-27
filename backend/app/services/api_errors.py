"""Catálogo público de erros da Mago API.

Os códigos são estáveis para clientes; mensagens podem evoluir sem que o
consumidor precise interpretar stack traces ou detalhes do provider.
"""

from __future__ import annotations

from typing import Any


ERROR_CATALOG: dict[str, dict[str, Any]] = {
    "AUTHENTICATION_REQUIRED": {
        "http_status": 401,
        "title": "Authentication required",
        "retryable": False,
    },
    "INVALID_API_KEY": {
        "http_status": 401,
        "title": "Invalid API key",
        "retryable": False,
    },
    "MISSING_SCOPE": {
        "http_status": 403,
        "title": "Missing scope",
        "retryable": False,
    },
    "INVALID_ARGUMENT": {
        "http_status": 400,
        "title": "Invalid argument",
        "retryable": False,
    },
    "IDEMPOTENCY_KEY_REQUIRED": {
        "http_status": 400,
        "title": "Idempotency key required",
        "retryable": False,
    },
    "IDEMPOTENCY_CONFLICT": {
        "http_status": 409,
        "title": "Idempotency conflict",
        "retryable": False,
    },
    "REQUEST_IN_PROGRESS": {
        "http_status": 409,
        "title": "Request in progress",
        "retryable": True,
    },
    "IDEMPOTENCY_STORE_UNAVAILABLE": {
        "http_status": 503,
        "title": "Idempotency store unavailable",
        "retryable": True,
    },
    "JOB_ACCEPTANCE_FAILED": {
        "http_status": 503,
        "title": "Job acceptance failed",
        "retryable": True,
    },
    "JOB_NOT_READY": {
        "http_status": 202,
        "title": "Job not ready",
        "retryable": True,
    },
    "NOT_FOUND": {
        "http_status": 404,
        "title": "Not found",
        "retryable": False,
    },
    "RESULT_EXPIRED": {
        "http_status": 410,
        "title": "Result expired",
        "retryable": False,
    },
    "RESULT_UNAVAILABLE": {
        "http_status": 409,
        "title": "Result unavailable",
        "retryable": False,
    },
    "RESULT_NOT_FOUND": {
        "http_status": 404,
        "title": "Result not found",
        "retryable": False,
    },
    "FORMAT_MISMATCH": {
        "http_status": 409,
        "title": "Format mismatch",
        "retryable": False,
    },
    "PAGINATION_NOT_READY": {
        "http_status": 501,
        "title": "Pagination not ready",
        "retryable": False,
    },
    "CANCELLED": {
        "http_status": 409,
        "title": "Cancelled",
        "retryable": False,
    },
    "JOB_FAILED": {
        "http_status": 500,
        "title": "Job failed",
        "retryable": False,
    },
    "UNAVAILABLE": {
        "http_status": 503,
        "title": "Temporarily unavailable",
        "retryable": True,
    },
    "DEADLINE_EXCEEDED": {
        "http_status": 504,
        "title": "Deadline exceeded",
        "retryable": False,
    },
    "INTERNAL_ERROR": {
        "http_status": 500,
        "title": "Internal error",
        "retryable": False,
    },
}


def catalog_entry(code: str) -> dict[str, Any]:
    entry = ERROR_CATALOG.get(code)
    if entry is not None:
        return entry
    return {
        "http_status": 500,
        "title": "Internal error",
        "retryable": False,
    }


def problem_code(code: str) -> str:
    """URL estável para documentação do problema."""
    return f"https://viral.vr766.com/problems/{code.lower().replace('_', '-')}"


def operation_error(
    code: str,
    detail: str,
    *,
    retryable: bool | None = None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Monta erro seguro para o campo `operation.error`."""
    entry = catalog_entry(code)
    payload: dict[str, Any] = {
        "type": problem_code(code),
        "code": code,
        "title": entry["title"],
        "detail": detail,
        "retryable": entry["retryable"] if retryable is None else bool(retryable),
    }
    if metadata:
        payload["metadata"] = {
            str(key): str(value)
            for key, value in metadata.items()
            if key and value is not None
        }
    return payload
