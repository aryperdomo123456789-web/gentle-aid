"""Ferramenta 5 — Recodificação e limpeza pós-Canva/CapCut/Premiere."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..services import ingest, jobs, media
from ..services.delivery import deliver
from ..services.sterilizer import normalize_fit, normalize_format, normalize_level
from ..services.validation import VIDEO_EXT, ValidationError, output_path, parse_json_object, save_upload

bp = Blueprint("canva_cleaner", __name__, url_prefix="/api/canva-cleaner")


@bp.post("/run")
def run_job():
    raw_mutation = request.form.get("mutation")
    mutation = normalize_level(raw_mutation)
    bitrate = request.form.get("bitrate", "auto")

    if raw_mutation not in (None, "") and mutation is None:
        return jsonify(error="Nível de mutação inválido."), 400
    if mutation is None:
        mutation = "media"
    if bitrate != "auto" and not bitrate.endswith("k"):
        return jsonify(error="Perfil de bitrate inválido."), 400

    try:
        source_card = parse_json_object(request.form.get("source_card"), field="source_card")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    video_format = normalize_format(request.form.get("video_format"))
    format_fit = normalize_fit(request.form.get("format_fit"))
    source_url = (request.form.get("url") or "").strip()
    job = jobs.create_job(
        "canva",
        meta={
            "mutation": mutation,
            "bitrate": bitrate,
            "video_format": video_format,
            "format_fit": format_fit,
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
        jobs.fail(job["job_id"], "Envie um arquivo ou selecione um vídeo na pesquisa.")
        return jsonify(error="Envie um arquivo ou selecione um vídeo na pesquisa."), 400

    jobs.submit(job["job_id"], lambda jid: _work(jid, src, mutation, bitrate, source_url, video_format, format_fit))
    return jsonify(job), 202


def _work(
    job_id: str,
    src: Path | None,
    mutation: str,
    bitrate: str,
    source_url: str = "",
    video_format: str = "original",
    format_fit: str = "cover",
) -> None:
    src = ingest.resolve_source(src, source_url, job_id)
    jobs.stage(job_id, "esterilizando", "Destruindo metadados ISO/Canva e recodificando em H.264/AAC.", progress=20)

    dst = output_path("canva", job_id, "_clean.mp4")
    report = media.sterilize(
        src,
        dst,
        job_id=job_id,
        level=mutation,
        bitrate=bitrate,
        video_format=video_format,
        format_fit=format_fit,
    )
    src.unlink(missing_ok=True)

    deliver(job_id, dst, report, message="Vídeo esterilizado: virgem, único e sem rastro de origem.")
