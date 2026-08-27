"""Autenticação e autorização do data plane público da Mago API.

Este módulo é intencionalmente separado da sessão web do painel. A API pública
usa chaves de alta entropia emitidas pelo control plane e nunca coloca o segredo
bruto em ``g`` ou em logs; somente metadados sanitizados da chave são anexados à
requisição.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar
from uuid import uuid4

from flask import Response, g, jsonify, request

from . import release_keys
from .api_errors import catalog_entry, problem_code

_VIEW = TypeVar("_VIEW", bound=Callable[..., Any])


class ApiAuthError(RuntimeError):
    """Erro interno de autenticação/autorização já convertido em resposta."""


def request_id() -> str:
    """Retorna um identificador de correlação por request sem confiar no cliente."""
    current = getattr(g, "mago_request_id", None)
    if current:
        return str(current)
    value = f"req_{uuid4().hex}"
    g.mago_request_id = value
    return value


def _problem_type(code: str) -> str:
    slug = code.lower().replace("_", "-")
    return f"https://viral.vr766.com/problems/{slug}"


def problem_response(
    status: int,
    code: str,
    detail: str,
    *,
    retryable: bool | None = None,
    retry_after_seconds: int | None = None,
    field_errors: list[dict[str, Any]] | None = None,
) -> Response:
    """Cria uma resposta RFC 9457-like sem detalhes internos ou segredos."""
    entry = catalog_entry(code)
    payload: dict[str, Any] = {
        "type": problem_code(code),
        "title": entry["title"],
        "status": status,
        "code": code,
        "detail": detail,
        "instance": request.path,
        "request_id": request_id(),
        "retryable": entry["retryable"] if retryable is None else bool(retryable),
        "retry_after_seconds": retry_after_seconds,
        "field_errors": field_errors or [],
    }
    response = jsonify(payload)
    response.status_code = status
    response.content_type = "application/problem+json"
    response.headers["X-Request-Id"] = payload["request_id"]
    if retry_after_seconds is not None:
        response.headers["Retry-After"] = str(max(1, int(retry_after_seconds)))
    return response


def extract_raw_key() -> str:
    """Extrai a chave de headers aceitos, nunca de query string ou body."""
    direct = request.headers.get("X-API-Key", "").strip()
    if direct:
        return direct

    authorization = request.headers.get("Authorization", "").strip()
    scheme, separator, value = authorization.partition(" ")
    if separator and scheme.lower() == "bearer":
        return value.strip()
    return ""


def _scopes(info: dict[str, Any]) -> set[str]:
    values = info.get("scopes") or []
    return {str(value).strip() for value in values if str(value).strip()}


def _scope_allowed(info: dict[str, Any], required_scope: str) -> bool:
    granted = _scopes(info)
    if "admin" in granted:
        return True
    if required_scope in granted:
        return True
    # Um escopo de recurso não concede escrita por acidente.
    resource, separator, action = required_scope.partition(":")
    return separator == ":" and f"{resource}:*" in granted


def require_api_key(*required_scopes: str) -> Callable[[_VIEW], _VIEW]:
    """Protege uma rota do data plane com autenticação e escopos.

    O decorator registra somente metadados públicos da chave em
    ``g.mago_api_key``. O segredo bruto é descartado após o hash ser validado.
    """

    def decorator(view: _VIEW) -> _VIEW:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any):
            raw_key = extract_raw_key()
            if not raw_key:
                return problem_response(
                    401,
                    "AUTHENTICATION_REQUIRED",
                    "Envie uma chave em X-API-Key ou Authorization: Bearer.",
                )

            info = release_keys.validate_key(raw_key)
            if not info:
                return problem_response(
                    401,
                    "INVALID_API_KEY",
                    "A chave está ausente, inválida, expirada ou revogada.",
                )

            for scope in required_scopes:
                if not _scope_allowed(info, scope):
                    return problem_response(
                        403,
                        "MISSING_SCOPE",
                        f"A chave não possui o escopo necessário: {scope}.",
                    )

            # Apenas metadados sanitizados; jamais guardar raw_key.
            g.mago_api_key = {
                "id": info.get("id"),
                "prefix": info.get("prefix"),
                "scopes": sorted(_scopes(info)),
                "expires_at": info.get("expires_at"),
            }
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

    return decorator


def current_api_key() -> dict[str, Any]:
    """Retorna metadados da chave depois que ``require_api_key`` passou."""
    info = getattr(g, "mago_api_key", None)
    if not isinstance(info, dict) or not info.get("id"):
        raise RuntimeError("current_api_key() chamado fora de uma rota protegida.")
    return info
