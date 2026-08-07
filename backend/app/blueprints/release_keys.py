"""Administração de chaves de liberação para consumo externo do SaaS."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import release_keys
from ..services.auth import current_user

bp = Blueprint("release_keys", __name__, url_prefix="/api/access-keys")


def _require_owner():
    actor = current_user()
    if not actor:
        return None, (jsonify(error="Sessão expirada ou ausente."), 401)
    if actor.get("role") != "owner":
        return None, (jsonify(error="Sem permissão para acessar este painel."), 403)
    return actor, None


@bp.get("")
def list_release_keys():
    actor, error = _require_owner()
    if error:
        return error
    return jsonify(keys=release_keys.list_keys())


@bp.post("")
def create_release_key():
    actor, error = _require_owner()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    label = str(payload.get("label", "")).strip()
    scopes = payload.get("scopes")
    try:
        expires_in_days = int(payload.get("expires_in_days", 30))
    except (TypeError, ValueError):
        return jsonify(error="Informe a validade em dias."), 400

    try:
        created = release_keys.create_key(
            actor,
            label=label or "Chave de liberação",
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(key=created), 201


@bp.delete("/<key_id>")
def revoke_release_key(key_id: str):
    actor, error = _require_owner()
    if error:
        return error

    try:
        revoked = release_keys.revoke_key(actor, key_id)
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403
    except ValueError as exc:
        return jsonify(error=str(exc)), 404
    return jsonify(key=revoked)


@bp.post("/validate")
def validate_release_key():
    payload = request.get_json(silent=True) or {}
    raw_key = str(
        payload.get("key")
        or request.headers.get("X-Api-Key")
        or request.headers.get("Authorization", "").removeprefix("Bearer ")
        or ""
    ).strip()
    info = release_keys.validate_key(raw_key)
    if not info:
        return jsonify(error="Chave inválida, expirada ou revogada."), 401
    return jsonify(ok=True, key=info)
