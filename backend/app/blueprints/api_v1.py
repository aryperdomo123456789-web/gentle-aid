"""Data plane público da Mago API v1.

Este blueprint não reutiliza as rotas administrativas do painel. Ele expõe
somente recursos públicos versionados e devolve objetos sanitizados, sempre com
ownership baseado na API key autenticada.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, jsonify, request, send_file, url_for
from werkzeug.utils import secure_filename

from ..config import config
from ..services import idempotency, jobs, transcribe, validation
from ..services.api_auth import current_api_key, problem_response, request_id, require_api_key

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

_ALLOWED_OUTPUTS = {"srt", "vtt", "json", "text"}
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,160}$")
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._~-]{16,255}$")


def _safe_job_id(value: str) -> bool:
    return bool(_JOB_ID_RE.fullmatch(value))


def _key_owner() -> str:
    return str(current_api_key()["id"])


def _owner_of(job: dict[str, Any]) -> str | None:
    meta = job.get("meta") or {}
    if not isinstance(meta, dict):
        return None
    value = meta.get("api_key_id") or meta.get("consumer_id")
    return str(value) if value else None


def _owns(job: dict[str, Any]) -> bool:
    return _owner_of(job) == _key_owner()


def _api_status(job: dict[str, Any]) -> str:
    status = str(job.get("status") or "")
    expires_at = job.get("expires_at")
    if status == "done" and isinstance(expires_at, str) and expires_at:
        try:
            expires = datetime.fromisoformat(expires_at)
            if expires <= datetime.now(timezone.utc):
                return "expired"
        except ValueError:
            pass
    return {
        "done": "succeeded",
        "error": "failed",
    }.get(status, status or "failed")


def _artifact_path(job: dict[str, Any]) -> Path | None:
    """Retorna somente um output dentro do storage; rejeita path traversal."""
    artifacts = job.get("artifacts") or []
    if not isinstance(artifacts, list):
        return None
    storage_root = config.storage_dir.resolve()
    for item in artifacts:
        if not isinstance(item, dict) or item.get("kind") != "api-output":
            continue
        raw = str(item.get("path") or "")
        if not raw:
            continue
        try:
            candidate = Path(raw).resolve()
            if candidate.is_relative_to(storage_root) and candidate.is_file():
                return candidate
        except (OSError, RuntimeError, ValueError):
            continue
    return None


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    status = _api_status(job)
    result_path = _artifact_path(job) if status == "succeeded" else None
    job_id = str(job.get("job_id") or "")
    payload: dict[str, Any] = {
        "id": job_id,
        "object": "job",
        "type": "transcription",
        "status": status,
        "progress": int(job.get("progress") or (100 if status == "succeeded" else 0)),
        "stage": job.get("stage"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "expires_at": job.get("expires_at"),
        "poll_url": url_for("api_v1.get_job", job_id=job_id, _external=True),
        "result_url": (
            url_for("api_v1.get_job_result", job_id=job_id, _external=True)
            if result_path
            else None
        ),
        "error": None,
        "api_version": "v1",
    }
    if status == "failed":
        payload["error"] = {
            "code": "JOB_FAILED",
            "detail": str(job.get("message") or "O processamento falhou."),
            "retryable": False,
        }
    return payload


def _parse_common_fields() -> tuple[str, str] | Response:
    language = (request.form.get("language") or "").strip()[:20]
    output_format = (request.form.get("output_format") or "srt").strip().lower()
    if output_format not in _ALLOWED_OUTPUTS:
        return problem_response(
            400,
            "INVALID_ARGUMENT",
            "output_format deve ser srt, vtt, json ou text.",
            field_errors=[{"field": "output_format", "reason": "unsupported_value"}],
        )
    return language, output_format


def _file_fingerprint(path: Path, *, language: str, output_format: str, filename: str) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return idempotency.request_hash(
        request.method,
        request.path,
        language,
        output_format,
        secure_filename(filename),
        str(path.stat().st_size),
        digest.hexdigest(),
    )


def _format_timestamp(seconds: float, *, vtt: bool) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _render_segments(segments: list[transcribe.Segment], output_format: str, language: str) -> str:
    if output_format == "text":
        return "\n".join(segment.text.strip() for segment in segments if segment.text.strip()) + "\n"
    if output_format == "json":
        return json.dumps(
            {
                "language": language or None,
                "segments": [segment.dict() for segment in segments],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"

    vtt = output_format == "vtt"
    lines = ["WEBVTT", ""] if vtt else []
    for index, segment in enumerate(segments, start=1):
        start = _format_timestamp(segment.start, vtt=vtt)
        end = _format_timestamp(max(segment.end, segment.start + 0.05), vtt=vtt)
        if not vtt:
            lines.append(str(index))
        lines.extend([f"{start} --> {end}", segment.text.strip(), ""])
    return "\n".join(lines)


def _run_transcription(job_id: str, source: Path, output_format: str, language: str) -> None:
    try:
        jobs.stage(job_id, "transcribing", "Transcrevendo o arquivo.", progress=10)
        segments, detected = transcribe.transcribe(
            source,
            job_id=job_id,
            language=language or None,
            word_timestamps=output_format == "json",
        )
        jobs.check_cancelled(job_id)
        content = _render_segments(segments, output_format, detected)
        output = validation.output_path("api", job_id, f".{output_format}")
        output.write_text(content, encoding="utf-8")
        jobs.register_artifact(job_id, output, "api-output")
        jobs.update(
            job_id,
            progress=100,
            stage="concluido",
            message="Transcrição concluída.",
            filename=output.name,
            size_bytes=output.stat().st_size,
            api_language=detected or language or None,
            api_output_format=output_format,
        )
    finally:
        source.unlink(missing_ok=True)


def _idempotency_key() -> str | Response:
    value = request.headers.get("Idempotency-Key", "").strip()
    if not value or not _IDEMPOTENCY_RE.fullmatch(value):
        return problem_response(
            400,
            "IDEMPOTENCY_KEY_REQUIRED",
            "Envie Idempotency-Key com pelo menos 16 caracteres seguros.",
        )
    return value


def _replay_or_reserve(key: str, fingerprint: str) -> dict[str, Any] | Response | None:
    try:
        previous = idempotency.reserve(
            _key_owner(), key, fingerprint, resource_id=getattr(request, "mago_job_id", None)
        )
    except idempotency.IdempotencyConflict:
        return problem_response(
            409,
            "IDEMPOTENCY_CONFLICT",
            "A Idempotency-Key foi usada com parâmetros diferentes.",
        )
    except (idempotency.IdempotencyRecordUnavailable, ValueError):
        return problem_response(
            503,
            "IDEMPOTENCY_STORE_UNAVAILABLE",
            "O armazenamento de idempotência ainda não está disponível.",
            retryable=True,
            retry_after_seconds=5,
        )
    if previous is None:
        return None
    if previous.get("code") == "REQUEST_IN_PROGRESS":
        return problem_response(
            409,
            "REQUEST_IN_PROGRESS",
            "A operação com esta Idempotency-Key ainda está em andamento.",
            retryable=True,
            retry_after_seconds=2,
        )
    response = previous.get("response")
    if not isinstance(response, dict):
        return problem_response(500, "IDEMPOTENCY_RECORD_INVALID", "Registro de retry inválido.")
    replay = jsonify(response)
    replay.status_code = int(previous.get("status_code") or 200)
    replay.headers["X-Idempotent-Replay"] = "true"
    return replay


@bp.get("/health")
def health():
    return jsonify(status="ok", api_version="v1")


@bp.get("/capabilities")
@require_api_key("catalog:read")
def capabilities():
    return jsonify(
        api_version="v1",
        data=[
            {
                "id": "transcription",
                "status": "available",
                "input_formats": sorted(validation.AUDIO_EXT | validation.VIDEO_EXT),
                "output_formats": sorted(_ALLOWED_OUTPUTS),
                "limits": {
                    "max_upload_bytes": config.max_upload_bytes,
                    "jobs_concurrent": config.max_workers,
                },
            }
        ],
    )


@bp.post("/transcriptions")
@require_api_key("transcribe:write")
def create_transcription():
    key = _idempotency_key()
    if isinstance(key, Response):
        return key
    fields = _parse_common_fields()
    if isinstance(fields, Response):
        return fields
    language, output_format = fields
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return problem_response(
            400,
            "INVALID_ARGUMENT",
            "Envie um arquivo no campo file.",
            field_errors=[{"field": "file", "reason": "required"}],
        )

    job = jobs.create_job(
        "api-transcription",
        meta={
            "api_key_id": _key_owner(),
            "consumer_id": _key_owner(),
            "api_version": "v1",
            "output_format": output_format,
        },
    )
    job_id = job["job_id"]
    expires_at = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(timespec="seconds")
    jobs.update(job_id, expires_at=expires_at)
    try:
        source = validation.save_upload(
            uploaded,
            job_id,
            validation.AUDIO_EXT | validation.VIDEO_EXT,
        )
        fingerprint = _file_fingerprint(
            source,
            language=language,
            output_format=output_format,
            filename=uploaded.filename,
        )
        request.mago_job_id = job_id
        replay = _replay_or_reserve(key, fingerprint)
        if replay is not None:
            jobs.delete(job_id)
            return replay

        public = _public_job(job)
        jobs.submit(
            job_id,
            lambda jid: _run_transcription(jid, source, output_format, language),
        )
        idempotency.record(
            _key_owner(),
            key,
            status_code=202,
            response=public,
            resource_id=job_id,
        )
    except validation.ValidationError as exc:
        jobs.delete(job_id)
        return problem_response(400, "INVALID_ARGUMENT", str(exc))
    except (OSError, ValueError, idempotency.IdempotencyRecordUnavailable) as exc:
        jobs.delete(job_id)
        try:
            idempotency.release(_key_owner(), key)
        except idempotency.IdempotencyRecordUnavailable:
            pass
        return problem_response(
            503,
            "JOB_ACCEPTANCE_FAILED",
            "Não foi possível aceitar o job; tente novamente com a mesma Idempotency-Key.",
            retryable=True,
            retry_after_seconds=5,
        )
    except Exception:
        jobs.delete(job_id)
        try:
            idempotency.release(_key_owner(), key)
        except idempotency.IdempotencyRecordUnavailable:
            pass
        return problem_response(
            500,
            "INTERNAL_ERROR",
            "Falha interna ao aceitar o job.",
        )

    response = jsonify(public)
    response.status_code = 202
    response.headers["Location"] = url_for("api_v1.get_job", job_id=job_id, _external=True)
    response.headers["X-Request-Id"] = request_id()
    return response


@bp.get("/jobs")
@require_api_key("jobs:read")
def list_jobs():
    try:
        page_size = int(request.args.get("page_size", "50"))
    except ValueError:
        return problem_response(400, "INVALID_ARGUMENT", "page_size deve ser um inteiro.")
    page_size = max(1, min(100, page_size))
    status_filter = (request.args.get("status") or "").strip()
    items = [job for job in jobs.list_jobs(limit=500) if _owns(job)]
    if status_filter:
        if status_filter not in {"queued", "running", "succeeded", "failed", "cancelled", "expired"}:
            return problem_response(400, "INVALID_ARGUMENT", "status inválido.")
        items = [job for job in items if _api_status(job) == status_filter]
    # O primeiro slice usa cursor baseado em job_id assinado futuramente; até lá,
    # não aceita offset controlável. Sem token, entrega a primeira janela.
    if request.args.get("page_token"):
        return problem_response(
            501,
            "PAGINATION_NOT_READY",
            "A paginação por cursor será habilitada junto do armazenamento de tokens.",
        )
    page = items[:page_size]
    return jsonify(
        data=[_public_job(job) for job in page],
        has_more=len(items) > page_size,
        next_page_token=None,
    )


@bp.get("/jobs/<job_id>")
@require_api_key("jobs:read")
def get_job(job_id: str):
    if not _safe_job_id(job_id):
        return problem_response(404, "NOT_FOUND", "Job não encontrado.")
    job = jobs.get(job_id)
    if not job or not _owns(job):
        return problem_response(404, "NOT_FOUND", "Job não encontrado.")
    return jsonify(_public_job(job))


@bp.post("/jobs/<job_id>/cancel")
@require_api_key("jobs:write")
def cancel_job(job_id: str):
    if not _safe_job_id(job_id):
        return problem_response(404, "NOT_FOUND", "Job não encontrado.")
    key = _idempotency_key()
    if isinstance(key, Response):
        return key
    job = jobs.get(job_id)
    if not job or not _owns(job):
        return problem_response(404, "NOT_FOUND", "Job não encontrado.")
    fingerprint = idempotency.request_hash(request.method, request.path, job_id)
    replay = _replay_or_reserve(key, fingerprint)
    if replay is not None:
        return replay
    cancelled = jobs.request_cancel(job_id) or jobs.get(job_id)
    public = _public_job(cancelled or job)
    try:
        idempotency.record(
            _key_owner(),
            key,
            status_code=202,
            response=public,
            resource_id=job_id,
        )
    except idempotency.IdempotencyRecordUnavailable:
        return problem_response(503, "IDEMPOTENCY_STORE_UNAVAILABLE", "Tente novamente.", retryable=True)
    response = jsonify(public)
    response.status_code = 202
    response.headers["Location"] = url_for("api_v1.get_job", job_id=job_id, _external=True)
    return response


@bp.get("/jobs/<job_id>/result")
@require_api_key("results:read")
def get_job_result(job_id: str):
    if not _safe_job_id(job_id):
        return problem_response(404, "NOT_FOUND", "Resultado não encontrado.")
    job = jobs.get(job_id)
    if not job or not _owns(job):
        return problem_response(404, "NOT_FOUND", "Resultado não encontrado.")
    status = _api_status(job)
    if status in {"queued", "running"}:
        return problem_response(
            202,
            "JOB_NOT_READY",
            "O job ainda está sendo processado.",
            retryable=True,
            retry_after_seconds=5,
        )
    if status == "expired":
        return problem_response(410, "RESULT_EXPIRED", "O resultado expirou.")
    if status != "succeeded":
        return problem_response(409, "RESULT_UNAVAILABLE", "O job não possui resultado disponível.")
    output = _artifact_path(job)
    if not output:
        return problem_response(404, "RESULT_NOT_FOUND", "O resultado não foi encontrado.")
    requested = (request.args.get("format") or output.suffix.lstrip(".")).lower()
    expected = output.suffix.lstrip(".")
    if requested != expected:
        return problem_response(409, "FORMAT_MISMATCH", "O formato solicitado não corresponde ao resultado criado.")
    return send_file(
        output,
        as_attachment=True,
        download_name=output.name,
        mimetype={"srt": "application/x-subrip", "vtt": "text/vtt", "json": "application/json", "text": "text/plain"}.get(expected, "application/octet-stream"),
        max_age=0,
    )


@bp.get("/usage")
@require_api_key("usage:read")
def usage():
    own = [job for job in jobs.list_jobs(limit=500) if _owns(job)]
    return jsonify(
        period="current",
        requests=None,
        jobs=len(own),
        limits={
            "requests_per_minute": 60,
            "jobs_concurrent": config.max_workers,
            "max_upload_bytes": config.max_upload_bytes,
        },
    )
