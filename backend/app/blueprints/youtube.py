"""Ferramenta 1 — Download e bypass universal de YouTube."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..config import config
from ..services import jobs, media
from ..services.delivery import deliver
from ..services.sterilizer import normalize_level
from ..services.validation import (
    YOUTUBE_RE,
    ValidationError,
    clean_text,
    output_path,
    public_url,
)

bp = Blueprint("youtube", __name__, url_prefix="/api/youtube")


@bp.post("/bypass")
def bypass():
    payload = request.get_json(silent=True) or {}
    urls = [str(u).strip() for u in payload.get("urls", []) if str(u).strip()]

    if not urls:
        return jsonify(error="Informe pelo menos um link do YouTube."), 400
    if len(urls) > 20:
        return jsonify(error="Máximo de 20 links por lote."), 400
    for url in urls:
        if not YOUTUBE_RE.match(url):
            return jsonify(error=f"Link inválido: {url}"), 400

    try:
        nicho = clean_text(payload.get("nicho"), max_length=60, field="nicho")
        keyword = clean_text(payload.get("keyword"), max_length=80, field="keyword")
        source_card = payload.get("source_card")
        if source_card is not None and not isinstance(source_card, dict):
            raise ValidationError("Campo 'source_card' deve ser um objeto JSON.")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    raw_intensity = payload.get("intensity")
    intensity = normalize_level(raw_intensity)
    if raw_intensity not in (None, "") and intensity is None:
        return jsonify(error="Intensidade inválida."), 400
    if intensity is None:
        intensity = "media"

    job = jobs.create_job(
        "youtube",
        meta={
            "urls": urls,
            "nicho": nicho,
            "keyword": keyword,
            "intensity": intensity,
            **({"source_card": source_card} if source_card else {}),
        },
    )
    jobs.submit(job["job_id"], lambda jid: _work(jid, urls, intensity))
    return jsonify(job), 202


def _work(job_id: str, urls: list[str], intensity: str) -> None:
    outputs: list[dict] = []
    total = len(urls)
    last_report = None
    last_dst: Path | None = None

    for index, url in enumerate(urls, start=1):
        jobs.check_cancelled(job_id)
        jobs.stage(job_id, "baixando", f"[{index}/{total}] Baixando {url}.", progress=int((index - 1) / total * 100))
        raw = config.uploads_dir / f"{job_id}_{index}.mp4"
        media.run(
            [
                config.ytdlp_bin,
                "-f",
                "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
                "--merge-output-format",
                "mp4",
                "--no-playlist",
                "-o",
                str(raw),
                url,
            ],
            job_id=job_id,
        )

        dst = output_path("youtube", job_id, f"_{index}_bypass.mp4")
        jobs.stage(job_id, "esterilizando", f"[{index}/{total}] Esterilizando com mutação '{intensity}'.")
        report = media.sterilize(raw, dst, job_id=job_id, level=intensity)
        raw.unlink(missing_ok=True)

        outputs.append(
            {
                "url": url,
                "download_url": public_url(dst),
                "filename": dst.name,
                "md5_before": report.md5_before,
                "md5_after": report.md5_after,
            }
        )
        last_report, last_dst = report, dst
        jobs.update(job_id, progress=int(index / total * 100), outputs=outputs)

    if last_report and last_dst:
        deliver(
            job_id,
            last_dst,
            last_report,
            message=f"{total} vídeo(s) entregues virgens com bypass '{intensity}'.",
            extra={"outputs": outputs},
        )
