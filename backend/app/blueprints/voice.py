"""Ferramenta 4 — Conversão de voz V2V preservando o timing original."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..services import ingest, jobs, media
from ..services.delivery import deliver
from ..services.sterilizer import normalize_level
from ..services.validation import AUDIO_EXT, ValidationError, output_path, parse_json_object, save_upload

bp = Blueprint("voice", __name__, url_prefix="/api/voice")

# Presets de timbre: (pitch em semitons, fator de formante)
VOICES = {
    "masc_grave": (-3.0, 0.94),
    "masc_jovem": (-1.0, 0.98),
    "fem_suave": (3.0, 1.06),
    "fem_energetica": (4.5, 1.08),
    "narrador": (-2.0, 0.96),
}
FORMATS = {"wav": ".wav", "mp3": ".mp3", "aac": ".m4a"}
SAMPLE_RATE = 48000


@bp.get("/catalog")
def catalog():
    return jsonify(
        voices=[
            {"id": vid, "semitones": semi, "formant": formant}
            for vid, (semi, formant) in VOICES.items()
        ],
        formats=list(FORMATS),
        levels=list(LEVELS),
    )


@bp.post("/convert")
def convert():
    target = request.form.get("target_voice", "masc_grave")
    fmt = request.form.get("format", "wav")
    preserve = request.form.get("preserve_timing", "strict")
    raw_mutation = request.form.get("mutation")
    mutation = normalize_level(raw_mutation)

    if target not in VOICES:
        return jsonify(error="Timbre alvo inválido."), 400
    if fmt not in FORMATS:
        return jsonify(error="Formato de saída inválido."), 400
    if raw_mutation not in (None, "") and mutation is None:
        return jsonify(error="Nível de mutação inválido."), 400
    if mutation is None:
        mutation = "leve"

    try:
        source_card = parse_json_object(request.form.get("source_card"), field="source_card")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    job = jobs.create_job(
        "voice",
        meta={
            "target": target,
            "format": fmt,
            "timing": preserve,
            "mutation": mutation,
            **({"source_card": source_card} if source_card else {}),
        },
    )
    source_url = (request.form.get("url") or "").strip()
    src: Path | None = None
    if request.files.get("audio"):
        try:
            src = save_upload(request.files.get("audio"), job["job_id"], AUDIO_EXT)
        except ValidationError as exc:
            jobs.update(job["job_id"], status="error", message=str(exc))
            return jsonify(error=str(exc)), 400
    elif not ingest.is_supported_url(source_url):
        jobs.update(job["job_id"], status="error", message="Envie um áudio ou selecione um vídeo na pesquisa.")
        return jsonify(error="Envie um áudio ou selecione um vídeo na pesquisa."), 400

    jobs.submit(job["job_id"], lambda jid: _work(jid, src, target, fmt, mutation, source_url))
    return jsonify(job), 202


def _work(
    job_id: str, src: Path | None, target: str, fmt: str, mutation: str, source_url: str = ""
) -> None:
    src = ingest.resolve_source(src, source_url, job_id)
    semitones, formant = VOICES[target]
    ratio = 2 ** (semitones / 12)
    jobs.update(job_id, progress=25)
    jobs.log(job_id, f"Convertendo timbre para '{target}' ({semitones:+.1f} semitons)")

    # asetrate muda pitch e velocidade; atempo devolve a duração original.
    timbre_chain = [
        f"asetrate={int(SAMPLE_RATE * ratio)}",
        f"aresample={SAMPLE_RATE}",
        f"atempo={1 / ratio:.6f}",
        f"equalizer=f=2500:width_type=h:width=1200:g={(formant - 1) * 12:.2f}",
        "dynaudnorm=f=200:g=5",
    ]

    dst = output_path("voice", job_id, FORMATS[fmt])
    report = media.sterilize(
        src,
        dst,
        job_id=job_id,
        level=mutation,
        extra_audio_filters=timbre_chain,
    )
    src.unlink(missing_ok=True)

    deliver(job_id, dst, report, message="Voz convertida com timing original e áudio sem rastro.")
