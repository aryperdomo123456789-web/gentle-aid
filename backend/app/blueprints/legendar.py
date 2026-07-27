"""Ferramenta 3 — Legendagem dinâmica com esterilização na mesma passada."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..services import ingest, jobs, media
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

STYLES = set(media.SUBTITLE_STYLES)
POSITIONS = set(media.SUBTITLE_ALIGNMENT)


@bp.post("/run")
def run_job():
    style = request.form.get("style", "viral")
    position = request.form.get("position", "center")
    raw_mutation = request.form.get("mutation")
    mutation = normalize_level(raw_mutation)

    if style not in STYLES or position not in POSITIONS:
        return jsonify(error="Estilo ou posição inválidos."), 400
    if raw_mutation not in (None, "") and mutation is None:
        return jsonify(error="Nível de mutação inválido."), 400
    if mutation is None:
        mutation = "media"

    try:
        srt_text = clean_text(request.form.get("srt"), max_length=20000, field="srt")
        source_card = parse_json_object(request.form.get("source_card"), field="source_card")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    source_url = (request.form.get("url") or "").strip()
    job = jobs.create_job(
        "legendar",
        meta={
            "style": style,
            "position": position,
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
            jobs.update(job["job_id"], status="error", message=str(exc))
            return jsonify(error=str(exc)), 400
    elif not ingest.is_supported_url(source_url):
        jobs.update(job["job_id"], status="error", message="Envie um arquivo ou selecione um vídeo na pesquisa.")
        return jsonify(error="Envie um arquivo ou selecione um vídeo na pesquisa."), 400

    jobs.submit(
        job["job_id"],
        lambda jid: _work(jid, src, srt_text, style, position, mutation, source_url),
    )
    return jsonify(job), 202


def _work(
    job_id: str,
    src: Path | None,
    srt_text: str,
    style: str,
    position: str,
    mutation: str,
    source_url: str = "",
) -> None:
    src = ingest.resolve_source(src, source_url, job_id)
    jobs.update(job_id, progress=20)

    srt_path = output_path("legendar", job_id, ".srt")
    duration = media.probe_duration(src)
    if srt_text.strip():
        content = srt_text if "-->" in srt_text else _plain_to_srt(srt_text, duration)
    else:
        jobs.log(job_id, "Nenhuma transcrição enviada — gerando cartela padrão.")
        content = _plain_to_srt("Legenda automática", duration)
    srt_path.write_text(content, encoding="utf-8")

    dst = output_path("legendar", job_id, "_legendado.mp4")
    jobs.log(job_id, f"Queimando legendas (estilo {style}, posição {position}) + esterilização '{mutation}'")
    report = media.burn_subtitles(
        src, srt_path, dst, job_id=job_id, style=style, position=position, mutation=mutation
    )
    src.unlink(missing_ok=True)

    deliver(job_id, dst, report, message="Vídeo legendado e entregue virgem, sem rastro de origem.")


def _plain_to_srt(text: str, duration: float) -> str:
    words = text.split() or ["Legenda"]
    chunks = [" ".join(words[i : i + 6]) for i in range(0, len(words), 6)]
    total = duration or len(chunks) * 2.0
    step = total / len(chunks)

    def stamp(seconds: float) -> str:
        ms = int(seconds * 1000)
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines: list[str] = []
    for i, chunk in enumerate(chunks):
        lines += [str(i + 1), f"{stamp(i * step)} --> {stamp((i + 1) * step)}", chunk, ""]
    return "\n".join(lines)
