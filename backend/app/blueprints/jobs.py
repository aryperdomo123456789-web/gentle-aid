"""Central de histórico / consulta de jobs."""

from __future__ import annotations

from flask import Blueprint, jsonify

from ..services import jobs

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@bp.get("")
@bp.get("/")
def list_all():
    return jsonify(jobs=jobs.list_jobs())


@bp.get("/<job_id>")
def detail(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Job não encontrado."), 404
    return jsonify(job)
