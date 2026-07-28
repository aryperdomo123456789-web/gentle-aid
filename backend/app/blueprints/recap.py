"""Ferramenta 7 — Recap narrado de filmes, séries e vídeos longos.

Ouve o áudio, lê as cenas, entende o arco da história e reconta com a sua voz.
Uso pretendido: conteúdo próprio ou recap comentado (trechos curtos com
narração nova por cima). Aceita apenas upload e link público, igual às demais
esteiras — não há caminho para catálogo de streaming.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..services import captions, ingest, jobs, media, recap, transcribe, voice_forge
from ..services.delivery import deliver
from ..services.recap import FORMATS, RecapError
from ..services.sterilizer import normalize_level
from ..services.validation import (
    VIDEO_EXT,
    ValidationError,
    clean_text,
    output_path,
    parse_json_object,
    save_upload,
)

bp = Blueprint("recap", __name__, url_prefix="/api/recap")

MAX_BLOCK_CHARS = 1500


@bp.get("/catalog")
def catalog():
    return jsonify(recap.catalog())


@bp.get("/blocks")
def blocks_list():
    return jsonify(blocks=recap.list_blocks())


@bp.post("/blocks")
def blocks_save():
    payload = request.get_json(silent=True) or {}
    try:
        entry = recap.save_block_preset(payload)
    except RecapError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(preset=entry, blocks=recap.list_blocks())


@bp.delete("/blocks/<preset_id>")
def blocks_delete(preset_id: str):
    if not recap.delete_block_preset(preset_id):
        return jsonify(error="Preset não encontrado."), 404
    return jsonify(blocks=recap.list_blocks())


@bp.post("/run")
def run_job():
    form = request.form

    fmt_id = (form.get("format") or "short").strip()
    fmt = FORMATS.get(fmt_id)
    if fmt is None:
        return jsonify(error="Formato de saída inválido."), 400

    try:
        target_seconds = int(form.get("target_seconds") or fmt["default_seconds"])
    except ValueError:
        return jsonify(error="Duração alvo inválida."), 400
    target_seconds = max(fmt["min_seconds"], min(fmt["max_seconds"], target_seconds))

    engine = (form.get("engine") or "forge").strip()
    if engine not in ("forge", "elevenlabs"):
        return jsonify(error="Motor de voz inválido."), 400

    persona_id = (form.get("persona_id") or "").strip()
    voice_id = (form.get("voice_id") or "").strip()
    persona = voice_forge.get(persona_id) if engine == "forge" else None
    if engine == "forge" and persona is None:
        return jsonify(error="Escolha uma voz própria (persona) do Voice Forge."), 400
    if engine == "elevenlabs" and not voice_id:
        return jsonify(error="Escolha uma voz realista do ElevenLabs."), 400

    try:
        ambience = float(form.get("ambience") or 0.12)
    except ValueError:
        return jsonify(error="Volume do áudio original inválido."), 400
    ambience = max(0.0, min(0.5, ambience))

    style_id = (form.get("style") or "neutro").strip()
    with_captions = (form.get("captions") or "1") not in ("0", "false", "nao", "não")
    caption_preset = (form.get("caption_preset") or "hormozi").strip()
    use_vision = (form.get("vision") or "1") not in ("0", "false", "nao", "não")

    raw_mutation = form.get("mutation")
    mutation = normalize_level(raw_mutation) or "media"
    if raw_mutation not in (None, "") and normalize_level(raw_mutation) is None:
        return jsonify(error="Nível de esterilização inválido."), 400

    try:
        source_card = parse_json_object(form.get("source_card"), field="source_card")
        blocks = {
            "abertura": clean_text(form.get("abertura"), max_length=MAX_BLOCK_CHARS, field="abertura"),
            "meio": clean_text(form.get("meio"), max_length=MAX_BLOCK_CHARS, field="meio"),
            "fecho": clean_text(form.get("fecho"), max_length=MAX_BLOCK_CHARS, field="fecho"),
        }
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    if not transcribe.available():
        return jsonify(error=transcribe.missing_key_message()), 400
    if not recap.text_ai_available():
        return jsonify(
            error=(
                "O recap precisa de um LLM para entender a história: cadastre em /apis a chave "
                "da DeepSeek, Groq, OpenRouter ou Mistral."
            )
        ), 400

    source_url = (form.get("url") or "").strip()
    job = jobs.create_job(
        "recap",
        meta={
            "format": fmt_id,
            "target_seconds": target_seconds,
            "engine": engine,
            "persona_id": persona_id,
            "voice_id": voice_id,
            "style": style_id,
            "ambience": ambience,
            "captions": with_captions,
            "caption_preset": caption_preset,
            "vision": use_vision,
            "mutation": mutation,
            "url": source_url,
            **({"source_card": source_card} if source_card else {}),
        },
    )

    src: Path | None = None
    if request.files.get("video"):
        try:
            src = save_upload(request.files.get("video"), job["job_id"], VIDEO_EXT)
        except ValidationError as exc:
            jobs.fail(job["job_id"], str(exc))
            return jsonify(error=str(exc)), 400
    elif not ingest.is_supported_url(source_url):
        message = "Envie um arquivo ou cole um link público do vídeo."
        jobs.fail(job["job_id"], message)
        return jsonify(error=message), 400

    jobs.submit(
        job["job_id"],
        lambda jid: _work(
            jid,
            src,
            source_url,
            fmt=fmt,
            target_seconds=target_seconds,
            engine=engine,
            persona=persona,
            voice_id=voice_id,
            style_id=style_id,
            ambience=ambience,
            with_captions=with_captions,
            caption_preset=caption_preset,
            use_vision=use_vision,
            mutation=mutation,
            blocks=blocks,
        ),
    )
    return jsonify(job), 202


def _work(
    job_id: str,
    src: Path | None,
    source_url: str,
    *,
    fmt: dict,
    target_seconds: int,
    engine: str,
    persona,
    voice_id: str,
    style_id: str,
    ambience: float,
    with_captions: bool,
    caption_preset: str,
    use_vision: bool,
    mutation: str,
    blocks: dict[str, str],
) -> None:
    from ..config import config

    src = ingest.resolve_source(src, source_url, job_id)
    workdir = config.uploads_dir / f"{job_id}_recap"
    raw = workdir / "recap_raw.mp4"
    burned = workdir / "recap_legendado.mp4"
    ass_path = workdir / "recap.ass"

    try:
        duration = max(1.0, media.probe_duration(src))
        jobs.stage(job_id, "ouvindo", "Transcrevendo a fala com timestamps.", progress=12)
        segments, _detected = transcribe.transcribe(src, job_id=job_id)

        shots = []
        if use_vision:
            jobs.stage(job_id, "assistindo", "Lendo as cenas do vídeo com IA multimodal.", progress=28)
            shots = recap.describe_shots(src, duration, workdir, job_id)

        brief = recap.build_brief(segments, shots, duration, job_id)
        beats = recap.write_beats(
            brief,
            segments,
            shots,
            duration=duration,
            target_seconds=target_seconds,
            style_id=style_id,
            blocks=blocks,
            job_id=job_id,
        )

        voice = persona.base_voice if persona is not None else voice_id
        rate = int(getattr(persona, "rate", 0) or 0) if persona is not None else 0
        workdir.mkdir(parents=True, exist_ok=True)
        recap.narrate_and_assemble(
            src,
            beats,
            raw,
            workdir=workdir,
            width=fmt["width"],
            height=fmt["height"],
            frame_mode=fmt["frame_mode"],
            ambience=ambience,
            engine=engine,
            voice=voice,
            rate=rate,
            persona=persona,
            source_duration=duration,
            job_id=job_id,
        )

        suffix = "_recap_916.mp4" if fmt["id"] == "short" else "_recap_169.mp4"
        dst = output_path("recap", job_id, suffix)

        if with_captions:
            jobs.stage(job_id, "legendando", "Queimando a legenda animada da narração.", progress=90)
            lines = recap.caption_lines(beats)
            ass_path.write_text(
                captions.build_ass(
                    lines,
                    preset_id=caption_preset,
                    video_width=fmt["width"],
                    video_height=fmt["height"],
                ),
                encoding="utf-8",
            )
            report = media.burn_ass(raw, ass_path, dst, job_id=job_id, mutation=mutation)
        else:
            jobs.stage(job_id, "esterilizando", "Gerando o arquivo final com hash inédito.", progress=92)
            report = media.sterilize(raw, dst, job_id=job_id, level=mutation)

        deliver(
            job_id,
            dst,
            report,
            message=f"Recap narrado pronto · {len(beats)} blocos · {fmt['label']}.",
            extra={
                "recap_brief": brief,
                "recap_beats": [beat.dict() for beat in beats],
                "recap_shots": [shot.dict() for shot in shots],
            },
        )
    finally:
        recap.sweep(raw, burned, ass_path, workdir, src)
