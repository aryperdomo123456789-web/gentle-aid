"""Rotas de autenticação e gestão de usuários."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, jsonify, request

from ..services.auth import (
    clear_session_cookie,
    create_user,
    current_session,
    current_user,
    delete_user,
    issue_session_cookie,
    list_users,
    login,
    logout,
    update_user,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _json_error(message: str, status: int = 400):
    return jsonify(error=message), status


def _require_actor() -> dict[str, Any] | None:
    user = current_user()
    if not user:
        return None
    return user


@bp.get("/me")
def me():
    session = current_session()
    if not session:
        # Mantém o cliente simples: ausência de sessão é uma resposta válida.
        return jsonify(user=None, login_at=None)
    return jsonify(user=session["user"], login_at=session["login_at"])


@bp.post("/login")
def do_login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))
    if not email or not password:
        return _json_error("Email e senha são obrigatórios.")

    try:
        user, token, login_at = login(email, password)
    except ValueError as exc:
        return _json_error(str(exc), 401)

    response = jsonify(user=user, login_at=login_at)
    issue_session_cookie(response, token)
    return response


@bp.post("/logout")
def do_logout():
    logout()
    response = jsonify(ok=True)
    clear_session_cookie(response)
    return response


@bp.get("/users")
def users():
    actor = _require_actor()
    if not actor:
        return _json_error("Sessão expirada ou ausente.", 401)
    if actor.get("role") != "owner":
        return _json_error("Sem permissão para listar usuários.", 403)
    return jsonify(users=list_users())


@bp.post("/users")
def create():
    actor = _require_actor()
    if not actor:
        return _json_error("Sessão expirada ou ausente.", 401)
    payload = request.get_json(silent=True) or {}
    try:
        user = create_user(
            actor,
            name=str(payload.get("name", "")),
            email=str(payload.get("email", "")),
            password=str(payload.get("password", "")),
            role=str(payload.get("role", "common")),
        )
    except PermissionError as exc:
        return _json_error(str(exc), 403)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify(user=user), 201


@bp.put("/users/<user_id>")
def edit(user_id: str):
    actor = _require_actor()
    if not actor:
        return _json_error("Sessão expirada ou ausente.", 401)
    payload = request.get_json(silent=True) or {}
    try:
        user = update_user(
            actor,
            user_id,
            name=payload.get("name"),
            email=payload.get("email"),
            password=payload.get("password"),
            role=payload.get("role"),
        )
    except PermissionError as exc:
        return _json_error(str(exc), 403)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify(user=user)


@bp.delete("/users/<user_id>")
def remove(user_id: str):
    actor = _require_actor()
    if not actor:
        return _json_error("Sessão expirada ou ausente.", 401)
    try:
        delete_user(actor, user_id)
    except PermissionError as exc:
        return _json_error(str(exc), 403)
    except ValueError as exc:
        return _json_error(str(exc), 400)
    return jsonify(ok=True)
