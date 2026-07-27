"""Ferramenta 3 — Estúdio de Legendas Virais (ASS animado + esterilização)."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..services import beatsync, captions, ingest, jobs, media, transcribe
from ..services.delivery import deliver
from ..services.sterilizer import normalize_level
from ..services.validation import (
    VIDEO_EXT,
    ValidationError,
    clean_text,
    parse_json_object,
    output_path,
    save_upload,
)

bp = Blueprint("legendar", __name__, url_prefix="/api/legendar")

POSITIONS = set(captions.POSITIONS)


@bp.get("/presets")
def list_presets():
    return jsonify(
        presets=captions.preset_catalog(),
        animations=list(captions.ANIMATIONS),
        positions=list(captions.POSITIONS),
        transcription=transcribe.available(),
    )


def _float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(request.form.get(name, default))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


@bp.post("/run")
def run_job():
    preset = captions.resolve_preset(request.form.get("preset") or request.form.get("style"))
    position = request.form.get("position", "bottom")
    animation = (request.form.get("animation") or "auto").strip().lower()
    raw_mutation = request.form.get("mutation")
    mutation = normalize_level(raw_mutation)

    if position not in POSITIONS:
        return jsonify(error="Posição inválida."), 400
    if animation not in captions.ANIMATIONS:
        return jsonify(error="Animação inválida."), 400
    if raw_mutation not in (None, "") and mutation is None:
        return jsonify(error="Nível de mutação inválido."), 400
    if mutation is None:
        mutation = "media"

    try:
        srt_text = clean_text(request.form.get("srt"), max_length=200000, field="srt")
        source_card = parse_json_object(request.form.get("source_card"), field="source_card")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    style_opts = {
        "preset": preset["id"],
        "position": position,
        "animation": animation,
        "uppercase": request.form.get("uppercase") in ("1", "true", "on"),
        "uppercase_set": request.form.get("uppercase") is not None,
        "font_scale": _float("font_scale", 1.0, 0.35, 1.8),
        "margin_ratio": _float("margin_ratio", 0.14, 0.02, 0.45),
        "words_per_line": int(_float("words_per_line", preset["words_per_line"], 1, 10)),
        "accent": (request.form.get("accent") or "").strip(),
        "primary": (request.form.get("primary") or "").strip(),
        "emoji": request.form.get("emoji") in ("1", "true", "on"),
        "language": (request.form.get("language") or "").strip() or None,
        # Sincroniza a legenda com a batida da música do próprio vídeo
        "beat_sync": request.form.get("beat_sync") in ("1", "true", "on"),
        "beat_strength": _float("beat_strength", 0.22, 0.05, 0.5),
    }

    source_url = (request.form.get("url") or "").strip()
    aspect = (request.form.get("aspect") or "auto").strip().lower()
    if aspect not in ("auto", "9:16", "16:9", "1:1"):
        aspect = "auto"
    job = jobs.create_job(
        "legendar",
        meta={
            "preset": preset["id"],
            "preset_label": preset["label"],
            "position": position,
            "animation": animation if animation != "auto" else preset["animation"],
            "mutation": mutation,
            "aspect": aspect,
            "beat_sync": request.form.get("beat_sync") in ("1", "true", "on"),
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
        msg = "Envie um arquivo ou selecione um vídeo na pesquisa."
        jobs.fail(job["job_id"], msg)
        return jsonify(error=msg), 400

    jobs.submit(
        job["job_id"],
        lambda jid: _work(jid, src, srt_text, style_opts, mutation, source_url),
    )
    return jsonify(job), 202


def _work(
    job_id: str,
    src: Path | None,
    srt_text: str,
    opts: dict,
    mutation: str,
    source_url: str = "",
) -> None:
    src = ingest.resolve_source(src, source_url, job_id)
    jobs.stage(job_id, "preparando", "Origem resolvida — analisando o vídeo.", progress=15)

    info = media.probe(src)
    width = info.width or 1080
    height = info.height or 1920
    max_words = int(opts["words_per_line"])

    lines: list[captions.Line] = []
    if srt_text.strip():
        if "-->" in srt_text:
            jobs.stage(job_id, "transcrevendo", "Usando o SRT enviado — redistribuindo por palavra.", progress=25)
            srt_lines = captions.parse_srt(srt_text)
            words = [w for line in srt_lines for w in line.words]
            lines = captions.group_words(words, max_words=max_words)
        else:
            jobs.stage(job_id, "transcrevendo", "Texto simples recebido — sincronizando com a duração.", progress=25)
            duration = max(1.0, info.duration or media.probe_duration(src))
            words = captions.spread_words(srt_text.strip(), 0.0, duration)
            lines = captions.group_words(words, max_words=max_words)
    else:
        jobs.stage(
            job_id,
            "transcrevendo",
            "Escutando o áudio para gerar legendas palavra a palavra.",
            progress=25,
        )
        segments, detected = transcribe.transcribe(
            src, job_id=job_id, language=opts["language"], word_timestamps=True
        )
        jobs.update(job_id, detected_language=detected)
        lines = captions.lines_from_segments(segments, max_words=max_words)

    if opts.get("beat_sync"):
        jobs.stage(job_id, "ritmo", "Analisando a trilha para achar a batida da música.", progress=42)
        beat_map = beatsync.detect_beats(src, duration=info.duration or 0.0)
        if beat_map.ok:
            lines = beatsync.snap_lines(lines, beat_map.beats, tolerance=opts["beat_strength"])
            jobs.update(job_id, bpm=beat_map.bpm, beat_confidence=beat_map.confidence)
            jobs.stage(
                job_id,
                "ritmo",
                f"Batida travada em {beat_map.bpm:.0f} BPM — legenda encaixada no ritmo.",
                progress=48,
            )
        else:
            jobs.stage(job_id, "ritmo", "Sem batida clara no áudio — mantendo o tempo da fala.", progress=48)

    if not lines:
        raise RuntimeError("Não foi possível montar as legendas — nenhum trecho de fala detectado.")

    ass_content = captions.build_ass(
        lines,
        preset_id=opts["preset"],
        video_width=width,
        video_height=height,
        position=opts["position"],
        animation=opts["animation"],
        uppercase=opts["uppercase"] if opts["uppercase_set"] else None,
        font_scale=opts["font_scale"],
        accent_hex=opts["accent"],
        primary_hex=opts["primary"],
        margin_ratio=opts["margin_ratio"],
        emoji=opts["emoji"],
    )
    ass_path = output_path("legendar", job_id, ".ass")
    ass_path.write_text(ass_content, encoding="utf-8")
    jobs.register_artifact(job_id, ass_path, "captions")

    srt_path = output_path("legendar", job_id, ".srt")
    srt_path.write_text(_lines_to_srt(lines), encoding="utf-8")
    jobs.register_artifact(job_id, srt_path, "captions")

    jobs.update(job_id, caption_lines=len(lines))
    dst = output_path("legendar", job_id, "_legendado.mp4")
    jobs.stage(
        job_id,
        "esterilizando",
        f"Queimando {len(lines)} bloco(s) no preset '{opts['preset']}' + esterilização '{mutation}'.",
        progress=55,
    )
    report = media.burn_ass(src, ass_path, dst, job_id=job_id, mutation=mutation)
    src.unlink(missing_ok=True)

    deliver(job_id, dst, report, message="Vídeo legendado e entregue virgem, sem rastro de origem.")


def _stamp(seconds: float) -> str:
    ms = int(max(0.0, seconds) * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _lines_to_srt(lines: list[captions.Line]) -> str:
    out: list[str] = []
    for index, line in enumerate(lines, start=1):
        out += [str(index), f"{_stamp(line.start)} --> {_stamp(line.end)}", line.text, ""]
    return "\n".join(out)
