"""Ferramenta 2 — TikTok: radar de tendências e clonagem 1:1 esterilizada."""

from __future__ import annotations

import json

from flask import Blueprint, jsonify, request

from ..config import config
from ..services import jobs, media
from ..services.delivery import deliver
from ..services.sterilizer import LEVELS
from ..services.validation import (
    TIKTOK_RE,
    ValidationError,
    clean_text,
    output_path,
)

bp = Blueprint("tiktok", __name__, url_prefix="/api/tiktok")


@bp.get("/trends")
def trends():
    try:
        nicho = clean_text(request.args.get("nicho"), max_length=60, field="nicho")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    region = (request.args.get("region") or "BR").upper()[:2]

    query = f"{nicho} {region}".strip()
    found: list[dict] = []

    try:
        out = media.run(
            [
                config.ytdlp_bin,
                "--flat-playlist",
                "--dump-single-json",
                "--playlist-end",
                "12",
                f"ytsearch12:tiktok {query}",
            ],
            timeout=120,
        )
        data = json.loads(out[out.index("{") :]) if "{" in out else {}
        for entry in data.get("entries", [])[:12]:
            found.append(
                {
                    "id": entry.get("id", ""),
                    "title": entry.get("title", "Sem título"),
                    "author": entry.get("uploader", "desconhecido"),
                    "views": int(entry.get("view_count") or 0),
                    "likes": int(entry.get("like_count") or 0),
                    "url": entry.get("url") or entry.get("webpage_url") or "",
                }
            )
    except Exception as exc:  # noqa: BLE001
        return jsonify(error=f"Radar indisponível: {exc}"), 502

    return jsonify(trends=found, nicho=nicho, region=region)


@bp.post("/clone")
def clone():
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    level = str(payload.get("intensity") or "media")

    if not url:
        return jsonify(error="Informe o link do vídeo."), 400
    if not (TIKTOK_RE.match(url) or url.startswith("https://")):
        return jsonify(error="Link inválido."), 400
    if level not in LEVELS:
        return jsonify(error="Intensidade inválida."), 400

    job = jobs.create_job("tiktok", meta={"url": url, "intensity": level})
    jobs.submit(job["job_id"], lambda jid: _work(jid, url, level))
    return jsonify(job), 202


def _work(job_id: str, url: str, level: str) -> None:
    raw = config.uploads_dir / f"{job_id}_src.mp4"
    jobs.log(job_id, f"Extraindo mídia de {url}")
    media.run(
        [config.ytdlp_bin, "-f", "b[ext=mp4]/b", "--no-playlist", "-o", str(raw), url],
        job_id=job_id,
    )

    jobs.update(job_id, progress=50)
    dst = output_path("tiktok", job_id, "_clone.mp4")
    jobs.log(job_id, f"Clonando 1:1 e esterilizando (nível {level})")
    report = media.sterilize(raw, dst, job_id=job_id, level=level)
    raw.unlink(missing_ok=True)

    deliver(job_id, dst, report, message="Clone pronto: arquivo virgem e sem rastro do original.")
