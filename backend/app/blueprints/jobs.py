"""Central de histórico / consulta de jobs (Jobs Center)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import jobs

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")


@bp.get("")
@bp.get("/")
def list_all():
    tool = (request.args.get("tool") or "").strip()
    status = (request.args.get("status") or "").strip()
    items = jobs.list_jobs()
    if tool and tool != "todos":
        items = [j for j in items if j.get("tool") == tool]
    if status and status != "todos":
        items = [j for j in items if j.get("status") == status]
    stats = {
        "total": len(items),
        "done": sum(1 for j in items if j.get("status") == "done"),
        "error": sum(1 for j in items if j.get("status") == "error"),
        "cancelled": sum(1 for j in items if j.get("status") == "cancelled"),
        "running": sum(1 for j in items if j.get("status") in {"running", "queued"}),
        "bytes": sum(int(j.get("size_bytes") or 0) for j in items),
    }
    return jsonify(jobs=items, stats=stats)


@bp.get("/<job_id>")
def detail(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Job não encontrado."), 404
    return jsonify(job)


@bp.delete("/<job_id>")
def remove(job_id: str):
    if not jobs.get(job_id):
        return jsonify(error="Job não encontrado."), 404
    jobs.delete(job_id)
    return jsonify(ok=True, job_id=job_id)


@bp.post("/<job_id>/cancel")
def cancel(job_id: str):
    if not jobs.get(job_id):
        return jsonify(error="Job não encontrado."), 404
    job = jobs.request_cancel(job_id)
    return jsonify(ok=True, job=job or jobs.get(job_id))
