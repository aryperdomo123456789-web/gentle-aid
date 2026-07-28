"""Ferramenta 7 — Fábrica de Cortes (vídeo longo → cortes virais legendados)."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..config import config
from ..services import captions, clipper, highlights, ingest, jobs, transcribe
from ..services.sterilizer import normalize_level
from ..services.validation import (
    AUDIO_EXT,
    VIDEO_EXT,
    ValidationError,
    clean_text,
    parse_json_object,
    save_upload,
)

bp = Blueprint("clips", __name__, url_prefix="/api/clips")


@bp.get("/options")
def options():
    return jsonify(
        niches=highlights.catalog(),
        aspects=list(clipper.ASPECTS),
        frames=list(clipper.FRAMES),
        presets=captions.preset_catalog(),
        positions=list(captions.POSITIONS),
        transcription=transcribe.available(),
        transcription_hint=None if transcribe.available() else transcribe.missing_key_message(),
        ai_ready=highlights.llm_available(),
        max_clips=highlights.MAX_CLIPS_HARD,
    )


@bp.post("/preview")
def preview():
    """Prévia da curadoria a partir de um SRT/transcrição já existente."""
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("srt") or "").strip()
    if not text:
        return jsonify(error="Envie a transcrição (SRT) para simular os cortes."), 400
    if len(text) > 400_000:
        return jsonify(error="Transcrição grande demais para a prévia."), 400

    lines = captions.parse_srt(text)
    if not lines:
        return jsonify(error="Não consegui ler esse SRT."), 400

    clips = highlights.find(
        lines,
        niche_id=str(payload.get("niche") or "auto"),
        min_seconds=float(payload.get("min_seconds") or 60),
        max_seconds=float(payload.get("max_seconds") or 180),
        max_clips=int(payload.get("max_clips") or 0),
        total_duration=lines[-1].end,
    )
    return jsonify(clips=clips, total=len(clips))


def _float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(request.form.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))

MAX_MANUAL_SEGMENTS = 40


def _parse_segments(raw: str | None) -> list[dict[str, object]]:
    """Cortes manuais da régua de edição: [{start, end, title}]."""
    text = (raw or "").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError("Lista de cortes manuais inválida.") from exc
    if not isinstance(data, list):
        raise ValidationError("Lista de cortes manuais deve ser um array.")
    if len(data) > MAX_MANUAL_SEGMENTS:
        raise ValidationError(f"Máximo de {MAX_MANUAL_SEGMENTS} cortes manuais por job.")

    out: list[dict[str, object]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValidationError("Cada corte manual deve ser um objeto.")
        try:
            start = float(item.get("start") or 0.0)
            end = float(item.get("end") or 0.0)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Tempos inválidos no corte {index + 1}.") from exc
        if start < 0 or end <= start:
            raise ValidationError(f"O corte {index + 1} precisa terminar depois de começar.")
        if end - start < 1.0:
            raise ValidationError(f"O corte {index + 1} é curto demais (mínimo 1s).")
        if end - start > 3600:
            raise ValidationError(f"O corte {index + 1} passa de 1 hora.")
        title = clean_text(
            str(item.get("title") or f"Corte manual {index + 1}"),
            max_length=120,
            field="title",
        )
        out.append({"start": start, "end": end, "title": title or f"Corte manual {index + 1}"})
    out.sort(key=lambda seg: float(seg["start"]))  # type: ignore[arg-type]
    return out



def _save_music(job_id: str) -> Path | None:
    file = request.files.get("music")
    if not file or not file.filename:
        return None
    ext = Path(file.filename).suffix.lower()
    if ext not in AUDIO_EXT:
        raise ValidationError(f"Trilha com extensão '{ext or 'desconhecida'}' não permitida.")
    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = config.uploads_dir / f"{job_id}_music{ext}"
    file.save(dest)
    if dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise ValidationError("Trilha vazia enviada.")
    jobs.register_artifact(job_id, dest, "input")
    return dest


@bp.post("/run")
def run_job():
    niche = (request.form.get("niche") or "auto").strip()
    aspect = (request.form.get("aspect") or "9:16").strip()
    frame = (request.form.get("frame") or "crop").strip()
    position = (request.form.get("caption_position") or "bottom").strip()
    preset_raw = (request.form.get("caption_preset") or "hormozi").strip()
    raw_mutation = request.form.get("mutation")
    mutation = normalize_level(raw_mutation)

    if niche not in highlights.NICHE_IDS:
        return jsonify(error="Nicho inválido."), 400
    if aspect not in clipper.ASPECTS:
        return jsonify(error="Formato inválido."), 400
    if frame not in clipper.FRAMES:
        return jsonify(error="Modo de enquadramento inválido."), 400
    if position not in captions.POSITIONS:
        return jsonify(error="Posição de legenda inválida."), 400
    if raw_mutation not in (None, "") and mutation is None:
        return jsonify(error="Nível de mutação inválido."), 400
    if mutation is None:
        mutation = "media"

    try:
        manual_segments = _parse_segments(request.form.get("segments"))
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    caption_preset: str | None = None
    if preset_raw and preset_raw != "none":
        caption_preset = captions.resolve_preset(preset_raw)["id"]

    # Modo manual sem legenda dispensa transcrição — corta direto na régua.
    if (not manual_segments or caption_preset) and not transcribe.available():
        return jsonify(error=transcribe.missing_key_message()), 400

    min_seconds = _float("min_seconds", 60, 8, 1200)
    max_seconds = _float("max_seconds", 180, 12, 1800)

    if max_seconds <= min_seconds:
        max_seconds = min_seconds + 15

    try:
        source_url = clean_text(request.form.get("url"), max_length=500, field="url")
        source_card = parse_json_object(request.form.get("source_card"), field="source_card")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    has_upload = bool(request.files.get("video") and request.files["video"].filename)
    if not has_upload and not source_url:
        return jsonify(error="Envie um vídeo longo ou cole um link."), 400

    job = jobs.create_job(
        "clips",
        meta={
            "niche": niche,
            "aspect": aspect,
            "frame": frame,
            "mode": "manual" if manual_segments else "auto",
            "manual_segments": manual_segments or None,
            "min_seconds": min_seconds,
            "max_seconds": max_seconds,
            "caption_preset": caption_preset,
            "caption_position": position,
            "mutation": mutation,
            "source_card": source_card,
        },
    )

    job_id = job["job_id"]

    try:
        src = save_upload(request.files.get("video"), job_id, VIDEO_EXT) if has_upload else None
        music = _save_music(job_id)
    except ValidationError as exc:
        jobs.fail(job_id, str(exc))
        return jsonify(error=str(exc)), 400

    language = (request.form.get("language") or "").strip() or None
    words_per_line = int(_float("words_per_line", 4, 1, 8))
    music_volume = _float("music_volume", 0.12, 0.02, 0.6)
    voice_volume = _float("voice_volume", 1.0, 0.2, 2.0)
    max_clips = int(_float("max_clips", 0, 0, highlights.MAX_CLIPS_HARD))
    use_ai = request.form.get("use_ai") not in ("0", "false", "off")

    def task(jid: str):
        local = ingest.resolve_source(src, source_url or None, jid)
        return clipper.generate(
            jid,
            src=local,
            niche_id=niche,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            max_clips=max_clips,
            aspect=aspect,
            frame=frame,
            caption_preset=caption_preset,
            caption_position=position,
            words_per_line=words_per_line,
            language=language,
            music=music,
            music_volume=music_volume,
            voice_volume=voice_volume,
            use_ai=use_ai,
            mutation=mutation,
        )

    jobs.submit(job_id, task)
    return jsonify(job), 202
