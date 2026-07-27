"""Central de APIs: leitura, troca e teste das chaves usadas pelo ecossistema."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import api_keys

bp = Blueprint("apis", __name__, url_prefix="/api/apis")


@bp.get("")
@bp.get("/")
def list_providers():
    items = api_keys.list_all()
    return jsonify(
        providers=items,
        total=len(items),
        configured=sum(1 for i in items if i["configured"]),
    )


@bp.put("/<provider_id>")
def update_provider(provider_id: str):
    if provider_id not in api_keys.PROVIDER_BY_ID:
        return jsonify(error="Provedor desconhecido."), 404

    payload = request.get_json(silent=True) or {}
    key = str(payload.get("key", "")).strip()
    note = str(payload.get("note", "")).strip()
    if not key:
        return jsonify(error="Informe a chave da API."), 400
    if len(key) < 8:
        return jsonify(error="Chave muito curta — confira se copiou o valor completo."), 400

    provider = api_keys.PROVIDER_BY_ID[provider_id]
    prefix = provider.get("prefix")
    if prefix and not key.startswith(prefix):
        return jsonify(error=f"A chave da {provider['name']} normalmente começa com '{prefix}'."), 400

    return jsonify(provider=api_keys.set_key(provider_id, key, note))


@bp.delete("/<provider_id>")
def delete_provider(provider_id: str):
    if provider_id not in api_keys.PROVIDER_BY_ID:
        return jsonify(error="Provedor desconhecido."), 404
    return jsonify(provider=api_keys.delete_key(provider_id))


@bp.post("/<provider_id>/test")
def test_provider(provider_id: str):
    if provider_id not in api_keys.PROVIDER_BY_ID:
        return jsonify(error="Provedor desconhecido."), 404
    result = api_keys.test_provider(provider_id)
    return jsonify(result=result, provider=api_keys.describe(provider_id))


@bp.post("/test-all")
def test_all():
    results = {}
    for provider in api_keys.PROVIDERS:
        if provider.get("test"):
            results[provider["id"]] = api_keys.test_provider(provider["id"])
    return jsonify(results=results, providers=api_keys.list_all())
