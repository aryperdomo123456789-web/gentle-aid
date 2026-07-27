"""Ferramenta 5 — Recodificação e limpeza pós-Canva."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..services import jobs, media
from ..services.validation import VIDEO_EXT, ValidationError, output_path, public_url, save_upload

bp = Blueprint("canva_cleaner", __name__, url_prefix="/api/canva-cleaner")

MUTATIONS = {"off", "leve", "media", "agressiva"}


@bp.post("/run")
def run_job():
    mutation = request.form.get("mutation", "media")
    bitrate = request.form.get("bitrate", "auto")
    strip = request.form.get("strip_metadata") == "1"

    if mutation not in MUTATIONS:
        return jsonify(error="Nível de mutação inválido."), 400
    if bitrate != "auto" and not bitrate.endswith("k"):
        return jsonify(error="Perfil de bitrate inválido."), 400

    job = jobs.create_job("canva", meta={"mutation": mutation, "bitrate": bitrate, "strip": strip})
    try:
        src = save_upload(request.files.get("video"), job["job_id"], VIDEO_EXT)
    except ValidationError as exc:
        jobs.update(job["job_id"], status="error", message=str(exc))
        return jsonify(error=str(exc)), 400

    jobs.submit(job["job_id"], lambda jid: _work(jid, src, mutation, bitrate, strip))
    return jsonify(job), 202


def _work(job_id: str, src: Path, mutation: str, bitrate: str, strip: bool) -> None:
    jobs.update(job_id, md5_before=media.md5(src), progress=20)
    jobs.log(job_id, "Removendo metadados ISO/Canva e recodificando em H.264/AAC")

    dst = output_path("canva", job_id, "_clean.mp4")
    media.sanitize_video(
        src,
        dst,
        job_id=job_id,
        mutation=mutation,
        bitrate=bitrate,
        strip_metadata=strip,
    )
    src.unlink(missing_ok=True)

    after = media.md5(dst)
    jobs.update(
        job_id,
        status="done",
        progress=100,
        message="Vídeo esterilizado com hash MD5 inédito.",
        download_url=public_url(dst),
        filename=dst.name,
        md5_after=after,
    )
