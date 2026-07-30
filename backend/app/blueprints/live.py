"""Estação de Live 24/7 — transmissão RTMP em loop (YouTube e TikTok).

Duas páginas no painel consomem este mesmo blueprint, mudando apenas a
plataforma. Toda a supervisão de processo mora em `services/streamer.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from ..config import config
from ..services import api_keys, streamer
from ..services.streamer import PLATFORMS, PRESETS, StreamerError
from ..services.validation import VIDEO_EXT

bp = Blueprint("live", __name__, url_prefix="/api/live")

MAX_PLAYLIST = 20


def _media_dir() -> Path:
    path = config.storage_dir / "_live" / "media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _platform_from(value: str | None) -> str:
    platform = (value or "").strip().lower()
    if platform not in PLATFORMS:
        raise StreamerError("Plataforma inválida (use youtube ou tiktok).")
    return platform


def _stored_key(platform: str) -> str:
    provider_id = PLATFORMS[platform]["provider_id"]
    try:
        return api_keys.get_key(provider_id) or ""
    except Exception:  # noqa: BLE001 - provider pode não existir no cofre
        return ""


def _resolve_library(names: list[str]) -> list[Path]:
    """Aceita apenas caminhos relativos dentro do storage — sem path traversal."""
    root = config.storage_dir.resolve()
    resolved: list[Path] = []
    for raw in names:
        rel = str(raw).lstrip("/").strip()
        if not rel:
            continue
        candidate = (root / rel).resolve()
        if not str(candidate).startswith(str(root)):
            raise StreamerError("Caminho de vídeo fora do storage.")
        if candidate.suffix.lower() not in VIDEO_EXT:
            raise StreamerError(f"Extensão não suportada: {candidate.name}")
        if not candidate.exists():
            raise StreamerError(f"Vídeo não encontrado no acervo: {candidate.name}")
        resolved.append(candidate)
    return resolved


@bp.get("/options")
def options():
    """Presets, plataformas e estado das chaves — alimenta as duas páginas."""
    platforms = []
    for platform, spec in PLATFORMS.items():
        platforms.append(
            {
                "id": platform,
                "label": spec["label"],
                "note": spec["note"],
                "default_url": spec["default_url"],
                "default_preset": streamer.DEFAULT_PRESET[platform],
                "key_configured": bool(_stored_key(platform)),
                "provider_id": spec["provider_id"],
            }
        )
    return jsonify(
        platforms=platforms,
        presets=[{"id": pid, **{k: v for k, v in preset.items()}} for pid, preset in PRESETS.items()],
    )


@bp.get("/library")
def library():
    """Vídeos prontos das outras ferramentas, disponíveis para a playlist."""
    root = config.storage_dir.resolve()
    items: list[dict[str, object]] = []
    for tool in ("youtube", "tiktok", "legendar", "canva", "studio", "recap", "voice"):
        base = config.tool_dir(tool)
        if not base.exists():
            continue
        for file in sorted(base.rglob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
            if not file.is_file() or file.suffix.lower() not in VIDEO_EXT:
                continue
            items.append(
                {
                    "tool": tool,
                    "name": file.name,
                    "path": file.resolve().relative_to(root).as_posix(),
                    "size_bytes": file.stat().st_size,
                    "modified_at": int(file.stat().st_mtime),
                }
            )
            if len(items) >= 120:
                break
    for file in sorted(_media_dir().glob("*")):
        if file.is_file() and file.suffix.lower() in VIDEO_EXT:
            items.append(
                {
                    "tool": "live",
                    "name": file.name,
                    "path": file.resolve().relative_to(root).as_posix(),
                    "size_bytes": file.stat().st_size,
                    "modified_at": int(file.stat().st_mtime),
                }
            )
    return jsonify(items=items)


@bp.get("/status")
def status():
    try:
        platform = _platform_from(request.args.get("platform"))
    except StreamerError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(streamer.status(platform))


@bp.get("/sessions")
def sessions():
    return jsonify(sessions=streamer.sessions())


@bp.post("/start")
def start():
    form = request.form
    try:
        platform = _platform_from(form.get("platform"))
    except StreamerError as exc:
        return jsonify(error=str(exc)), 400

    paths: list[Path] = []
    raw_paths = form.get("paths") or "[]"
    try:
        parsed = json.loads(raw_paths)
        if not isinstance(parsed, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return jsonify(error="Campo 'paths' deve ser uma lista JSON."), 400

    try:
        paths.extend(_resolve_library([str(p) for p in parsed]))
    except StreamerError as exc:
        return jsonify(error=str(exc)), 400

    for upload in request.files.getlist("videos"):
        if not upload or not upload.filename:
            continue
        name = secure_filename(upload.filename)
        if Path(name).suffix.lower() not in VIDEO_EXT:
            return jsonify(error=f"Extensão não permitida: {name}"), 400
        dest = _media_dir() / name
        upload.save(dest)
        if dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            return jsonify(error="Arquivo vazio enviado."), 400
        paths.append(dest)

    if not paths:
        return jsonify(error="Selecione ou envie pelo menos um vídeo."), 400
    if len(paths) > MAX_PLAYLIST:
        return jsonify(error=f"Máximo de {MAX_PLAYLIST} vídeos na playlist."), 400

    overlay = {
        "clock": form.get("overlay_clock") == "on",
        "counter": form.get("overlay_counter") == "on",
        "text": (form.get("overlay_text") or "").strip()[:120],
    }

    try:
        max_retries = int(form.get("max_retries") or 0)
    except ValueError:
        return jsonify(error="Limite de reconexões inválido."), 400

    try:
        session = streamer.start(
            platform,
            paths,
            rtmp_url=(form.get("rtmp_url") or "").strip(),
            stream_key=(form.get("stream_key") or "").strip() or _stored_key(platform),
            preset_id=(form.get("preset") or "").strip(),
            overlay=overlay,
            max_retries=max_retries,
        )
    except StreamerError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(session), 202


@bp.post("/stop")
def stop():
    payload = request.get_json(silent=True) or {}
    try:
        platform = _platform_from(payload.get("platform") or request.args.get("platform"))
        return jsonify(streamer.stop(platform))
    except StreamerError as exc:
        return jsonify(error=str(exc)), 400
