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


@bp.post("/inspect")
def inspect():
    """Dados completos de um link direto: métricas, legenda e player."""
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url") or "").strip()
    with_captions = payload.get("captions", True) is not False

    if not url:
        return jsonify(error="Cole o link do vídeo."), 400
    if len(url) > 500:
        return jsonify(error="URL muito longa."), 400

    try:
        data = discovery.inspect(url, with_captions=with_captions)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=f"Não foi possível analisar o link: {exc}"), 502

    return jsonify(data)
