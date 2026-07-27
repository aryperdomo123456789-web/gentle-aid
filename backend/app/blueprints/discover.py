"""Fluxo de descoberta compartilhado por todas as ferramentas.

`POST /api/discover/search` devolve os cards (descrição, curtidas, views,
comentários, shares, duração, data) com `embed_url` para assistir o conteúdo
antes de mandar para a esteira de codagem.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import discovery

bp = Blueprint("discover", __name__, url_prefix="/api/discover")


@bp.post("/search")
def search():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query") or payload.get("keyword") or "").strip()
    platform = str(payload.get("platform") or "auto").strip().lower()
    region = str(payload.get("region") or "BR").strip()
    limit = payload.get("limit") or 18

    if not query:
        return jsonify(error="Informe uma palavra-chave, @perfil ou URL."), 400
    if len(query) > 300:
        return jsonify(error="Consulta muito longa."), 400

    try:
        data = discovery.search(query, platform=platform, region=region, limit=int(limit))
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=f"Busca indisponível: {exc}"), 502

    return jsonify(data)
