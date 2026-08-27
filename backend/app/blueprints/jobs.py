"""Central de Jobs: consulta, rastro, auditoria, cancelamento e exclusão.

Todas as ferramentas do ecossistema gravam no mesmo registro, então este
blueprint é a única porta de entrada para histórico e ações de job.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import jobs
from ..services.auth import current_user

bp = Blueprint("jobs", __name__, url_prefix="/api/jobs")

_LIMITS = (1, 500)


def _require_session(*, owner: bool = False):
    user = current_user()
    if not user:
        return None, (jsonify(error="Sessão expirada ou ausente."), 401)
    if owner and user.get("role") != "owner":
        return None, (jsonify(error="Apenas o owner pode acessar esta trilha."), 403)
    return user, None


def _clamp_limit(raw: str | None, default: int = 200) -> int:
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(_LIMITS[0], min(_LIMITS[1], value))


@bp.get("")
@bp.get("/")
def list_all():
    _user, error = _require_session()
    if error:
        return error
    tool = (request.args.get("tool") or "").strip()
    status = (request.args.get("status") or "").strip()
    search = (request.args.get("q") or "").strip().lower()
    limit = _clamp_limit(request.args.get("limit"))

    items = jobs.list_jobs(limit=_LIMITS[1])
    total_all = len(items)
    if tool and tool != "todos":
        items = [j for j in items if j.get("tool") == tool]
    if status and status != "todos":
        if status == "running":
            items = [j for j in items if j.get("status") in {"running", "queued"}]
        else:
            items = [j for j in items if j.get("status") == status]
    if search:
        def matches(job: dict) -> bool:
            haystack = " ".join(
                str(job.get(key) or "")
                for key in ("job_id", "filename", "source_label", "source_url", "message")
            ).lower()
            return search in haystack

        items = [j for j in items if matches(j)]

    items = items[:limit]
    stats = jobs.summarize(items)
    stats["total_all"] = total_all
    return jsonify(jobs=items, stats=stats, tools=jobs.TOOL_LABELS)


@bp.get("/stats")
def stats_only():
    _user, error = _require_session(owner=True)
    if error:
        return error
    items = jobs.list_jobs()
    return jsonify(stats=jobs.summarize(items), tools=jobs.TOOL_LABELS)


@bp.get("/audit")
def audit_ledger():
    """Trilha append-only global — inclusive de jobs já excluídos."""
    _user, error = _require_session(owner=True)
    if error:
        return error
    limit = _clamp_limit(request.args.get("limit"), default=200)
    job_id = (request.args.get("job_id") or "").strip() or None
    return jsonify(entries=jobs.read_audit(limit=limit, job_id=job_id))


@bp.get("/<job_id>")
def detail(job_id: str):
    _user, error = _require_session()
    if error:
        return error
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="Job não encontrado."), 404
    return jsonify(job)


@bp.get("/<job_id>/trace")
def trace(job_id: str):
    """Rastro completo de um job: eventos estruturados + auditoria."""
    _user, error = _require_session(owner=True)
    if error:
        return error
    job = jobs.get(job_id)
    audit_entries = jobs.read_audit(limit=200, job_id=job_id)
    if not job and not audit_entries:
        return jsonify(error="Job não encontrado."), 404
    return jsonify(
        job_id=job_id,
        status=(job or {}).get("status"),
        stage=(job or {}).get("stage"),
        events=(job or {}).get("events") or [],
        log=(job or {}).get("log") or [],
        artifacts=(job or {}).get("artifacts") or [],
        audit=audit_entries,
    )


@bp.delete("/<job_id>")
def remove(job_id: str):
    _user, error = _require_session(owner=True)
    if error:
        return error
    if not jobs.get(job_id):
        return jsonify(error="Job não encontrado."), 404
    jobs.delete(job_id)
    return jsonify(ok=True, job_id=job_id)


@bp.post("/<job_id>/cancel")
def cancel(job_id: str):
    _user, error = _require_session()
    if error:
        return error
    if not jobs.get(job_id):
        return jsonify(error="Job não encontrado."), 404
    job = jobs.request_cancel(job_id)
    return jsonify(ok=True, job=job or jobs.get(job_id))
