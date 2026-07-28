"""Ferramenta 6 — Estúdio de Vídeo IA (prompt → vídeo pronto)."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, request

from ..config import config
from ..services import captions, edge_tts, jobs, storyboard, video_gen, visuals, voice_forge
from ..services.sterilizer import normalize_level
from ..services.validation import (
    AUDIO_EXT,
    VIDEO_EXT,
    ValidationError,
    clean_text,
)

bp = Blueprint("studio", __name__, url_prefix="/api/studio")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MEDIA_EXT = IMAGE_EXT | VIDEO_EXT


@bp.get("/options")
def options():
    return jsonify(
        styles=storyboard.styles(),
        looks=storyboard.LOOKS,
        modes=[
            {"id": "ia", "label": "Imagem IA grátis (Pollinations)", "free": True},
            {"id": "broll", "label": "B-roll real (Pexels/Pixabay)", "free": True},
            {"id": "upload", "label": "Mídia que eu subir", "free": True},
            {"id": "premium", "label": "Vídeo IA pago (slot)", "free": False},
        ],
        aspects=list(video_gen.ASPECTS),
        presets=captions.preset_catalog(),
        positions=list(captions.POSITIONS),
        voices=edge_tts.list_voices(),
        personas=voice_forge.list_personas(),
        llm_ready=storyboard.llm_available(),
        tts_ready=edge_tts.available(),
    )


@bp.post("/storyboard")
def make_storyboard():
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt") or "").strip()
    if len(prompt) < 8:
        return jsonify(error="Descreva a ideia do vídeo com pelo menos 8 caracteres."), 400
    if len(prompt) > 8000:
        return jsonify(error="O prompt excede 8000 caracteres."), 400

    plan = storyboard.plan(
        prompt,
        style_id=str(payload.get("style") or "neutro"),
        scenes=int(payload.get("scenes") or 8),
        seconds=int(payload.get("seconds") or 45),
        language=str(payload.get("language") or "português do Brasil"),
        instruction=str(payload.get("instruction") or "")[:1000],
    )
    return jsonify(plan)


def _scenes_from_request(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise ValidationError("Campo 'scenes' não é um JSON válido.") from exc
    if not isinstance(data, list) or not data:
        raise ValidationError("Envie ao menos uma cena no storyboard.")
    scenes: list[dict] = []
    for index, item in enumerate(data[: storyboard.MAX_SCENES]):
        if not isinstance(item, dict):
            continue
        narration = str(item.get("narration") or "").strip()
        if not narration:
            continue
        scenes.append(
            {
                "index": index,
                "narration": narration[:2000],
                "visual": str(item.get("visual") or narration)[:400],
                "query": str(item.get("query") or "")[:80],
            }
        )
    if not scenes:
        raise ValidationError("Nenhuma cena com narração foi enviada.")
    return scenes


def _save_media(job_id: str, prefix: str, allowed: set[str]) -> list[Path]:
    saved: list[Path] = []
    for index, file in enumerate(request.files.getlist(prefix)):
        if not file or not file.filename:
            continue
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed:
            raise ValidationError(f"Extensão '{ext or 'desconhecida'}' não permitida em {prefix}.")
        config.uploads_dir.mkdir(parents=True, exist_ok=True)
        dest = config.uploads_dir / f"{job_id}_{prefix}{index:02d}{ext}"
        file.save(dest)
        if dest.stat().st_size == 0:
            dest.unlink(missing_ok=True)
            raise ValidationError("Arquivo vazio enviado.")
        jobs.register_artifact(job_id, dest, "input")
        saved.append(dest)
    return saved


@bp.post("/run")
def run_job():
    mode = (request.form.get("mode") or "ia").strip().lower()
    aspect = (request.form.get("aspect") or "9:16").strip()
    look_id = (request.form.get("look") or "cartoon").strip()
    voice = (request.form.get("voice") or "pt-BR-AntonioNeural").strip()
    persona_id = (request.form.get("persona_id") or "").strip()
    position = (request.form.get("caption_position") or "bottom").strip()
    preset_raw = (request.form.get("caption_preset") or "hormozi").strip()
    mutation = normalize_level(request.form.get("mutation")) or "media"

    if mode not in visuals.MODES:
        return jsonify(error="Modo visual inválido."), 400
    if aspect not in video_gen.ASPECTS:
        return jsonify(error="Formato inválido."), 400
    if position not in captions.POSITIONS:
        return jsonify(error="Posição de legenda inválida."), 400
    if look_id not in storyboard.LOOK_IDS:
        return jsonify(error="Direção de arte inválida."), 400
    if not edge_tts.available():
        return jsonify(error="Motor de narração indisponível: instale `edge-tts` no servidor."), 400

    caption_preset: str | None = None
    if preset_raw and preset_raw != "none":
        caption_preset = captions.resolve_preset(preset_raw)["id"]

    try:
        scenes = _scenes_from_request(request.form.get("scenes") or "")
        title = clean_text(request.form.get("title"), max_length=200, field="title")
        rate_percent = max(-40, min(40, int(request.form.get("rate") or 0)))
        music_volume = max(0.02, min(0.6, float(request.form.get("music_volume") or 0.14)))
    except (ValidationError, ValueError) as exc:
        return jsonify(error=str(exc)), 400

    job = jobs.create_job(
        "studio",
        meta={
            "title": title,
            "mode": mode,
            "aspect": aspect,
            "look": look_id,
            "voice": voice,
            "persona_id": persona_id or None,
            "scenes": len(scenes),
            "caption_preset": caption_preset,
            "caption_position": position,
            "mutation": mutation,
        },
    )
    job_id = job["job_id"]
    jobs.update(job_id, source_kind="prompt", source_label=title or f"{len(scenes)} cena(s)")

    try:
        uploads = _save_media(job_id, "media", MEDIA_EXT)
        music_files = _save_media(job_id, "music", AUDIO_EXT)
    except ValidationError as exc:
        jobs.fail(job_id, str(exc))
        return jsonify(error=str(exc)), 400

    if mode == "upload" and not uploads:
        msg = "Modo 'Mídia que eu subir' precisa de pelo menos um arquivo."
        jobs.fail(job_id, msg)
        return jsonify(error=msg), 400

    look = storyboard.look(look_id)
    jobs.submit(
        job_id,
        lambda jid: video_gen.generate(
            jid,
            scenes=scenes,
            mode=mode,
            aspect=aspect,
            look_suffix=look["suffix"],
            voice=voice,
            persona_id=persona_id,
            rate_percent=rate_percent,
            uploads=uploads,
            music=music_files[0] if music_files else None,
            music_volume=music_volume,
            caption_preset=caption_preset,
            caption_position=position,
            mutation=mutation,
        ),
    )
    return jsonify(job), 202
