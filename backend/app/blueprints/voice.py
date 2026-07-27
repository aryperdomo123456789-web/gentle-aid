"""Ferramenta 4 — Conversão de voz V2V preservando o timing."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..config import config
from ..services import jobs, media
from ..services.validation import AUDIO_EXT, ValidationError, output_path, public_url, save_upload

bp = Blueprint("voice", __name__, url_prefix="/api/voice")

# Presets de timbre: (pitch em semitons, formante, ganho de brilho)
VOICES = {
    "masc_grave": (-3.0, 0.94),
    "masc_jovem": (-1.0, 0.98),
    "fem_suave": (3.0, 1.06),
    "fem_energetica": (4.5, 1.08),
    "narrador": (-2.0, 0.96),
}
FORMATS = {"wav": ".wav", "mp3": ".mp3", "aac": ".m4a"}


@bp.post("/convert")
def convert():
    target = request.form.get("target_voice", "masc_grave")
    fmt = request.form.get("format", "wav")
    preserve = request.form.get("preserve_timing", "strict")

    if target not in VOICES:
        return jsonify(error="Timbre alvo inválido."), 400
    if fmt not in FORMATS:
        return jsonify(error="Formato de saída inválido."), 400

    job = jobs.create_job("voice", meta={"target": target, "format": fmt, "timing": preserve})
    try:
        src = save_upload(request.files.get("audio"), job["job_id"], AUDIO_EXT)
    except ValidationError as exc:
        jobs.update(job["job_id"], status="error", message=str(exc))
        return jsonify(error=str(exc)), 400

    jobs.submit(job["job_id"], lambda jid: _work(jid, src, target, fmt, preserve))
    return jsonify(job), 202


def _work(job_id: str, src: Path, target: str, fmt: str, preserve: str) -> None:
    semitones, formant = VOICES[target]
    ratio = 2 ** (semitones / 12)
    jobs.update(job_id, md5_before=media.md5(src), progress=25)
    jobs.log(job_id, f"Convertendo timbre para '{target}' ({semitones:+.1f} semitons)")

    # asetrate muda pitch e velocidade; atempo devolve a duração original.
    sample_rate = 48000
    chain = [
        f"asetrate={int(sample_rate * ratio)}",
        f"aresample={sample_rate}",
        f"atempo={1 / ratio:.6f}",
        f"aformat=sample_rates={sample_rate}",
        f"equalizer=f=2500:width_type=h:width=1200:g={(formant - 1) * 12:.2f}",
        "dynaudnorm=f=200:g=5",
    ]
    if preserve == "natural":
        chain.append("atempo=1.0")

    dst = output_path("voice", job_id, FORMATS[fmt])
    codec = {"wav": ["-c:a", "pcm_s16le"], "mp3": ["-c:a", "libmp3lame", "-b:a", "320k"], "aac": ["-c:a", "aac", "-b:a", "192k"]}[fmt]

    media.run(
        [
            config.ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-i",
            str(src),
            "-af",
            ",".join(chain),
            *codec,
            "-map_metadata",
            "-1",
            str(dst),
        ],
        job_id=job_id,
    )
    src.unlink(missing_ok=True)

    jobs.update(
        job_id,
        status="done",
        progress=100,
        message="Conversão concluída mantendo o timing original.",
        download_url=public_url(dst),
        filename=dst.name,
        md5_after=media.md5(dst),
    )
