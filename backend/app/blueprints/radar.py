"""Radar Global — tendências reais e previsão de nichos."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import trends as trends_service
from ..services.validation import ValidationError, clean_text

bp = Blueprint("radar", __name__, url_prefix="/api/radar")


def _params() -> tuple[str, str]:
    nicho = clean_text(request.args.get("nicho"), max_length=60, field="nicho")
    region = (request.args.get("region") or "BR").upper()[:2]
    return nicho, region


@bp.get("/global")
def global_radar():
    try:
        nicho, region = _params()
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    refresh = request.args.get("refresh") in {"1", "true", "yes"}
    try:
        return jsonify(trends_service.radar(nicho, region, refresh=refresh))
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=f"Radar indisponível: {exc}"), 502


@bp.get("/snapshot")
def snapshot():
    try:
        nicho, region = _params()
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(
        snapshot=trends_service.load_radar_snapshot(nicho, region),
        nicho=nicho,
        region=region,
    )


@bp.get("/forecast")
def forecast():
    try:
        nicho, region = _params()
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    try:
        return jsonify(trends_service.forecast(nicho, region))
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=f"Previsão indisponível: {exc}"), 502


@bp.get("/searches")
def searches():
    region = (request.args.get("region") or "BR").upper()[:2]
    return jsonify(region=region, searches=trends_service.google_trends(region, 25))
