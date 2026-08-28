"""Data plane público da Mago API v1.

Este blueprint não reutiliza as rotas administrativas do painel. Ele expõe
somente recursos públicos versionados e devolve objetos sanitizados, sempre com
ownership baseado na API key autenticada.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, send_file, url_for
from werkzeug.utils import secure_filename

from ..config import config
from ..services import (
    idempotency,
    jobs,
    media,
    operations,
    persistent_queue,
    rate_limits,
    billing,
    transcribe,
    transcription_exports,
    validation,
    viral_clips,
    viral_insights,
)
from ..services.api_auth import current_api_key, problem_response, request_id, require_api_key

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

_ALLOWED_OUTPUTS = {"srt", "vtt", "json", "json_verbose", "text"}
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,160}$")
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9._~-]{16,255}$")


def _safe_job_id(value: str) -> bool:
    return bool(_JOB_ID_RE.fullmatch(value))


def _key_owner() -> str:
    return str(current_api_key()["id"])


def _billing_owner() -> str:
    return str(current_api_key().get("account_id") or _key_owner())


def _owner_of(job: dict[str, Any]) -> str | None:
    meta = job.get("meta") or {}
    if not isinstance(meta, dict):
        return None
    value = meta.get("api_key_id") or meta.get("consumer_id")
    return str(value) if value else None


def _owns(job: dict[str, Any]) -> bool:
    return _owner_of(job) == _key_owner()


def _api_status(job: dict[str, Any]) -> str:
    return {
        "PENDING": "queued",
        "RUNNING": "running",
        "SUCCEEDED": "succeeded",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
        "EXPIRED": "expired",
    }.get(operations.public_state(job), "failed")


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
    result_url = (
        url_for("api_v1.get_job_result", job_id=job_id, _external=True)
        if result_path
        else None
    )
    return operations.operation_view(job, result_url=result_url)


def _parse_common_fields() -> tuple[str, str] | Response:
    language = (request.form.get("language") or "").strip()[:20]
    output_format = (request.form.get("output_format") or "srt").strip().lower()
    if output_format not in _ALLOWED_OUTPUTS:
        return problem_response(
            400,
            "INVALID_ARGUMENT",
            "output_format deve ser srt, vtt, json, json_verbose ou text.",
            field_errors=[{"field": "output_format", "reason": "unsupported_value"}],
        )
    return language, output_format


def _parse_webhook_config() -> dict[str, str] | Response:
    from urllib.parse import urlparse
    nested = request.form.get("webhook")
    nested_data: dict[str, Any] = {}
    if nested:
        try:
            parsed_nested = json.loads(nested)
            if isinstance(parsed_nested, dict):
                nested_data = parsed_nested
        except json.JSONDecodeError:
            return problem_response(400, "INVALID_ARGUMENT", "webhook deve ser um objeto JSON válido.")
    url = str(nested_data.get("url") or request.form.get("webhook_url") or "").strip()
    secret = str(nested_data.get("secret") or request.form.get("webhook_secret") or "").strip()
    if not url and not secret:
        return {}
    if not url or not secret:
        return problem_response(400, "INVALID_ARGUMENT", "webhook_url e webhook_secret devem ser enviados juntos.")
    parsed = urlparse(url)
    if parsed.scheme != "https" and not current_app.testing:
        return problem_response(400, "INVALID_ARGUMENT", "webhook_url deve usar HTTPS.")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or len(url) > 2048:
        return problem_response(400, "INVALID_ARGUMENT", "webhook_url inválida.")
    if len(secret) < 32 or len(secret) > 512:
        return problem_response(400, "INVALID_ARGUMENT", "webhook_secret deve ter entre 32 e 512 caracteres.")
    return {"webhook_url": url, "webhook_secret": secret}


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


def _render_segments(
    segments: list[transcribe.Segment],
    output_format: str,
    language: str,
    *,
    duration_seconds: float | None = None,
) -> str:
    return transcription_exports.render_segments(
        segments,
        output_format,
        language=language,
        duration_seconds=duration_seconds,
    )


def _run_transcription(
    job_id: str,
    source: Path,
    output_format: str,
    language: str,
    *,
    cleanup_source: bool = True,
) -> None:
    try:
        jobs.stage(job_id, "transcribing", "Transcrevendo o arquivo.", progress=10)
        duration_seconds = max(0.1, media.probe_duration(source))
        segments, detected = transcribe.transcribe(
            source,
            job_id=job_id,
            language=language or None,
            word_timestamps=output_format in {"json", "json_verbose"},
        )
        jobs.check_cancelled(job_id)
        canonical = transcription_exports.verbose_payload(
            segments,
            language=detected,
            duration_seconds=duration_seconds,
        )
        content = _render_segments(
            segments,
            output_format,
            detected,
            duration_seconds=duration_seconds,
        )
        output = validation.output_path("api", job_id, f".{transcription_exports.extension_for(output_format)}")
        output.write_text(content, encoding="utf-8")
        jobs.register_artifact(job_id, output, "api-output")
        jobs.update(job_id, transcription=canonical)
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
        if cleanup_source:
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
@rate_limits.enforce()
def capabilities():
    plan_limits = rate_limits.limits(_key_owner())
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
                    "jobs_concurrent": plan_limits["max_concurrent_jobs"],
                    "requests_per_minute": plan_limits["requests_per_minute"],
                    "jobs_per_day": plan_limits["jobs_per_day"],
                    "audio_seconds_per_day": plan_limits["audio_seconds_per_day"],
                    "cost_units_per_day": plan_limits["cost_units_per_day"],
                },
            }
        ],
    )


@bp.post("/transcriptions")
@require_api_key("transcribe:write")
@rate_limits.enforce()
def create_transcription():
    key = _idempotency_key()
    if isinstance(key, Response):
        return key
    fields = _parse_common_fields()
    if isinstance(fields, Response):
        return fields
    language, output_format = fields
    webhook = _parse_webhook_config()
    if isinstance(webhook, Response):
        return webhook
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
            **webhook,
        },
    )
    job_id = job["job_id"]
    expires_at = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(timespec="seconds")
    jobs.update(job_id, expires_at=expires_at, clips_enabled=True)
    quota_reserved = False
    billing_reserved = False
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
        try:
            duration_seconds = max(0.1, float(media.probe_duration(source)))
        except (OSError, ValueError, TypeError):
            duration_seconds = 0.0
        cost_units = max(1.0, round(duration_seconds / 60.0, 3))
        jobs.update(
            job_id,
            estimated_audio_seconds=round(duration_seconds, 3),
            estimated_cost_units=cost_units,
        )
        request.mago_job_id = job_id
        replay = _replay_or_reserve(key, fingerprint)
        if replay is not None:
            jobs.delete(job_id)
            return replay

        try:
            billing.reserve_transcription(
                _billing_owner(),
                seconds=duration_seconds,
                storage_bytes=source.stat().st_size,
                resource_id=job_id,
                idempotency_key=key,
            )
            billing_reserved = True
            rate_limits.reserve_job(
                _key_owner(),
                job_id=job_id,
                idempotency_key=key,
                audio_seconds=duration_seconds,
                cost_units=cost_units,
            )
            quota_reserved = True
        except (rate_limits.LimitExceeded, billing.BillingLimitExceeded) as exc:
            if billing_reserved:
                try:
                    billing.release_reservation(_billing_owner(), resource_id=job_id, idempotency_key=key)
                except billing.BillingUnavailable:
                    pass
            jobs.delete(job_id)
            try:
                idempotency.release(_key_owner(), key)
            except idempotency.IdempotencyRecordUnavailable:
                pass
            return problem_response(
                429,
                exc.code,
                exc.detail,
                retryable=True,
                retry_after_seconds=getattr(exc, "retry_after_seconds", 3600),
            )

        public = _public_job(jobs.get(job_id) or job)
        persistent_queue.enqueue(
            job_id,
            "api-transcription",
            {
                "source_path": str(source),
                "output_format": output_format,
                "language": language,
            },
        )
        jobs.update(job_id, queue="persistent", queue_status="queued")
        idempotency.record(
            _key_owner(),
            key,
            status_code=202,
            response=public,
            resource_id=job_id,
        )
    except validation.ValidationError as exc:
        if billing_reserved:
            try:
                billing.release_reservation(_billing_owner(), resource_id=job_id, idempotency_key=key)
            except billing.BillingUnavailable:
                pass
        jobs.delete(job_id)
        return problem_response(400, "INVALID_ARGUMENT", str(exc))
    except (OSError, ValueError, persistent_queue.QueueUnavailable, rate_limits.UsageUnavailable, idempotency.IdempotencyRecordUnavailable) as exc:
        if quota_reserved:
            try:
                rate_limits.release_job(_key_owner(), job_id=job_id, idempotency_key=key)
            except rate_limits.UsageUnavailable:
                pass
        if billing_reserved:
            try:
                billing.release_reservation(_billing_owner(), resource_id=job_id, idempotency_key=key)
            except billing.BillingUnavailable:
                pass
        try:
            persistent_queue.discard(job_id)
        except persistent_queue.QueueUnavailable:
            pass
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
        if quota_reserved:
            try:
                rate_limits.release_job(_key_owner(), job_id=job_id, idempotency_key=key)
            except rate_limits.UsageUnavailable:
                pass
        if billing_reserved:
            try:
                billing.release_reservation(_billing_owner(), resource_id=job_id, idempotency_key=key)
            except billing.BillingUnavailable:
                pass
        try:
            persistent_queue.discard(job_id)
        except persistent_queue.QueueUnavailable:
            pass
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
@rate_limits.enforce()
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


@bp.get("/operations/<job_id>")
@require_api_key("jobs:read")
@rate_limits.enforce()
def get_operation(job_id: str):
    if not _safe_job_id(job_id):
        return problem_response(404, "NOT_FOUND", "Operação não encontrada.")
    job = jobs.get(job_id)
    if not job or not _owns(job):
        return problem_response(404, "NOT_FOUND", "Operação não encontrada.")
    return jsonify(_public_job(job))


@bp.get("/jobs/<job_id>")
@require_api_key("jobs:read")
@rate_limits.enforce()
def get_job(job_id: str):
    if not _safe_job_id(job_id):
        return problem_response(404, "NOT_FOUND", "Job não encontrado.")
    job = jobs.get(job_id)
    if not job or not _owns(job):
        return problem_response(404, "NOT_FOUND", "Job não encontrado.")
    return jsonify(_public_job(job))


@bp.post("/operations/<job_id>:cancel")
@require_api_key("jobs:write")
@rate_limits.enforce()
def cancel_operation(job_id: str):
    return cancel_job(job_id)


@bp.post("/jobs/<job_id>/cancel")
@require_api_key("jobs:write")
@rate_limits.enforce()
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
    try:
        rate_limits.release_active_job(_key_owner(), job_id=job_id)
    except rate_limits.UsageUnavailable:
        return problem_response(503, "USAGE_STORE_UNAVAILABLE", "O ledger de uso está temporariamente indisponível.", retryable=True, retry_after_seconds=5)
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
@rate_limits.enforce()
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
        mimetype=transcription_exports.mime_type(expected) if expected in transcription_exports.OUTPUT_FORMATS else transcription_exports.media_mime_type(expected),
        max_age=0,
    )


@bp.get("/transcriptions/<job_id>/export")
@require_api_key("results:read")
@rate_limits.enforce()
def export_transcription(job_id: str):
    """Renderiza novamente os segmentos canônicos em um formato protegido."""
    if not _safe_job_id(job_id):
        return problem_response(404, "NOT_FOUND", "Transcrição não encontrada.")
    job = jobs.get(job_id)
    if not job or not _owns(job):
        return problem_response(404, "NOT_FOUND", "Transcrição não encontrada.")
    status = _api_status(job)
    if status == "expired":
        return problem_response(410, "RESULT_EXPIRED", "O resultado expirou.")
    if status in {"queued", "running"}:
        return problem_response(202, "JOB_NOT_READY", "O job ainda está sendo processado.", retryable=True, retry_after_seconds=5)
    if status != "succeeded":
        return problem_response(409, "RESULT_UNAVAILABLE", "O job não possui resultado disponível.")

    requested = (request.args.get("format") or "srt").strip().lower()
    if requested not in {"srt", "vtt", "json_verbose", "json", "text"}:
        return problem_response(
            400,
            "INVALID_ARGUMENT",
            "format deve ser srt, vtt, json_verbose ou text.",
            field_errors=[{"field": "format", "reason": "unsupported_value"}],
        )

    canonical = job.get("transcription")
    if not isinstance(canonical, dict) or not isinstance(canonical.get("segments"), list):
        output = _artifact_path(job)
        expected = output.suffix.lstrip(".") if output else ""
        if output and expected == requested:
            return send_file(
                output,
                as_attachment=True,
                download_name=output.name,
                mimetype=transcription_exports.mime_type(requested),
                max_age=0,
            )
        return problem_response(409, "EXPORT_NOT_AVAILABLE", "Este job antigo não possui segmentos canônicos para exportação.")

    content = transcription_exports.render_payload(canonical, requested)
    extension = transcription_exports.extension_for(requested)
    return send_file(
        io.BytesIO(content.encode("utf-8")),
        as_attachment=True,
        download_name=f"{job_id}.{extension}",
        mimetype=transcription_exports.mime_type(requested),
        max_age=0,
    )


@bp.post("/transcriptions/<job_id>/clips")
@require_api_key("transcribe:write")
@rate_limits.enforce()
def create_clip(job_id: str):
    """Cria um job assíncrono de recorte a partir de uma transcrição concluída."""
    if not _safe_job_id(job_id):
        return problem_response(404, "NOT_FOUND", "Transcrição não encontrada.")
    parent = jobs.get(job_id)
    if not parent or not _owns(parent):
        return problem_response(404, "NOT_FOUND", "Transcrição não encontrada.")
    if _api_status(parent) != "succeeded":
        return problem_response(409, "RESULT_UNAVAILABLE", "A transcrição precisa estar concluída para gerar um clip.")
    transcription = parent.get("transcription")
    if not isinstance(transcription, dict) or not isinstance(transcription.get("segments"), list):
        return problem_response(409, "CLIP_SOURCE_UNAVAILABLE", "A transcrição não possui segmentos canônicos para gerar o clip.")
    source = Path(str(parent.get("source_path") or ""))
    try:
        source = viral_clips.source_in_storage(source)
    except viral_clips.ClipValidationError:
        return problem_response(409, "CLIP_SOURCE_UNAVAILABLE", "A mídia-fonte não está disponível para recorte.")

    key = _idempotency_key()
    if isinstance(key, Response):
        return key
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return problem_response(400, "INVALID_ARGUMENT", "Envie um objeto JSON com start_seconds e end_seconds.")
    try:
        start, end, duration = viral_clips.validate_window(
            body.get("start_seconds"),
            body.get("end_seconds"),
            transcription.get("duration_seconds") or parent.get("estimated_audio_seconds") or 0,
        )
    except viral_clips.ClipValidationError as exc:
        return problem_response(
            400,
            "CLIP_INVALID_WINDOW",
            str(exc),
            field_errors=[
                {"field": "start_seconds", "reason": "invalid_window"},
                {"field": "end_seconds", "reason": "invalid_window"},
            ],
        )

    max_clips = body.get("max_clips")
    insight = body.get("insight") if isinstance(body.get("insight"), dict) else None
    fingerprint = idempotency.request_hash(
        request.method,
        request.path,
        job_id,
        str(start),
        str(end),
        json.dumps(insight, sort_keys=True, ensure_ascii=False) if insight else "",
    )
    parent_meta = parent.get("meta") if isinstance(parent.get("meta"), dict) else {}
    webhook_meta = {key: parent_meta[key] for key in ("webhook_url", "webhook_secret") if parent_meta.get(key)}
    clip_job = jobs.create_job(
        "api-clip",
        meta={
            "api_key_id": _key_owner(),
            "consumer_id": _key_owner(),
            "api_version": "v1",
            "operation_type": "clip",
            "parent_job_id": job_id,
            "output_format": "mp4" if source.suffix.lower() in validation.VIDEO_EXT else "m4a",
            **webhook_meta,
        },
    )
    clip_id = clip_job["job_id"]
    expires_at = parent.get("expires_at")
    jobs.update(
        clip_id,
        expires_at=expires_at,
        parent_job_id=job_id,
        source_start_seconds=start,
        source_end_seconds=end,
        clip_duration_seconds=round(end - start, 3),
        source_path=str(source),
        clips_enabled=False,
    )
    request.mago_job_id = clip_id
    quota_reserved = False
    billing_reserved = False
    try:
        replay = _replay_or_reserve(key, fingerprint)
        if replay is not None:
            jobs.delete(clip_id)
            return replay
        billing.reserve_clip(
            _billing_owner(),
            resource_id=clip_id,
            idempotency_key=key,
        )
        billing_reserved = True
        rate_limits.reserve_job(
            _key_owner(),
            job_id=clip_id,
            idempotency_key=key,
            audio_seconds=0.0,
            cost_units=0.0,
        )
        quota_reserved = True
        payload = {
            "parent_job_id": job_id,
            "start_seconds": start,
            "end_seconds": end,
            "insight": insight,
            "max_clips": max_clips,
        }
        persistent_queue.enqueue(clip_id, "api-clip", payload)
        jobs.update(clip_id, queue="persistent", queue_status="queued")
        public = _public_job(jobs.get(clip_id) or clip_job)
        idempotency.record(_key_owner(), key, status_code=202, response=public, resource_id=clip_id)
    except (rate_limits.LimitExceeded, billing.BillingLimitExceeded) as exc:
        if billing_reserved:
            try:
                billing.release_reservation(_billing_owner(), resource_id=clip_id, idempotency_key=key)
            except billing.BillingUnavailable:
                pass
        jobs.delete(clip_id)
        try:
            idempotency.release(_key_owner(), key)
        except idempotency.IdempotencyRecordUnavailable:
            pass
        return problem_response(429, exc.code, exc.detail, retryable=getattr(exc, "retryable", False), retry_after_seconds=getattr(exc, "retry_after_seconds", 3600))
    except (persistent_queue.QueueUnavailable, rate_limits.UsageUnavailable, billing.BillingUnavailable, idempotency.IdempotencyRecordUnavailable, OSError, ValueError):
        if quota_reserved:
            try:
                rate_limits.release_job(_key_owner(), job_id=clip_id, idempotency_key=key)
            except rate_limits.UsageUnavailable:
                pass
        if billing_reserved:
            try:
                billing.release_reservation(_billing_owner(), resource_id=clip_id, idempotency_key=key)
            except billing.BillingUnavailable:
                pass
        try:
            persistent_queue.discard(clip_id)
        except persistent_queue.QueueUnavailable:
            pass
        jobs.delete(clip_id)
        try:
            idempotency.release(_key_owner(), key)
        except idempotency.IdempotencyRecordUnavailable:
            pass
        return problem_response(503, "JOB_ACCEPTANCE_FAILED", "Não foi possível aceitar o job de clip.", retryable=True, retry_after_seconds=5)
    response = jsonify(public)
    response.status_code = 202
    response.headers["Location"] = url_for("api_v1.get_operation", job_id=clip_id, _external=True)
    return response


@bp.get("/transcriptions/<job_id>/insights")
@require_api_key("results:read")
@rate_limits.enforce()
def get_transcription_insights(job_id: str):
    if not _safe_job_id(job_id):
        return problem_response(404, "NOT_FOUND", "Transcrição não encontrada.")
    job = jobs.get(job_id)
    if not job or not _owns(job):
        return problem_response(404, "NOT_FOUND", "Transcrição não encontrada.")
    if _api_status(job) != "succeeded":
        return problem_response(409, "RESULT_UNAVAILABLE", "A transcrição precisa estar concluída para gerar insights.")
    transcription = job.get("transcription")
    if not isinstance(transcription, dict):
        return problem_response(409, "CLIP_SOURCE_UNAVAILABLE", "O job não possui json_verbose canônico.")
    return jsonify(viral_insights.analyze_json_verbose(transcription))


@bp.get("/billing/usage")
@require_api_key("usage:read")
@rate_limits.enforce()
def billing_usage():
    return jsonify(
        billing=billing.usage_snapshot(_billing_owner()),
        technical=rate_limits.usage(_key_owner()),
    )


@bp.get("/usage")
@require_api_key("usage:read")
@rate_limits.enforce()
def usage():
    return jsonify(rate_limits.usage(_key_owner()))


@bp.post("/billing/webhooks/stripe")
def stripe_billing_webhook():
    from ..services import billing_webhooks
    try:
        result = billing_webhooks.process_stripe(
            request.get_data(cache=False),
            signature_header=request.headers.get("Stripe-Signature"),
        )
    except billing_webhooks.WebhookVerificationError as exc:
        return problem_response(400, "INVALID_WEBHOOK_SIGNATURE", str(exc))
    except billing_webhooks.WebhookPayloadError as exc:
        return problem_response(400, "INVALID_WEBHOOK_PAYLOAD", str(exc))
    except (billing.BillingUnavailable, OSError, ValueError):
        return problem_response(503, "BILLING_WEBHOOK_UNAVAILABLE", "Não foi possível processar o webhook agora.", retryable=True, retry_after_seconds=10)
    return jsonify(result), 200


@bp.post("/billing/webhooks/mercado-pago")
def mercado_pago_billing_webhook():
    from ..services import billing_webhooks
    try:
        result = billing_webhooks.process_mercado_pago(
            request.get_data(cache=False),
            signature_header=request.headers.get("x-signature"),
            request_id=request.headers.get("x-request-id"),
            data_id=request.args.get("data.id"),
        )
    except billing_webhooks.WebhookVerificationError as exc:
        return problem_response(400, "INVALID_WEBHOOK_SIGNATURE", str(exc))
    except billing_webhooks.WebhookPayloadError as exc:
        return problem_response(400, "INVALID_WEBHOOK_PAYLOAD", str(exc))
    except (billing.BillingUnavailable, OSError, ValueError):
        return problem_response(503, "BILLING_WEBHOOK_UNAVAILABLE", "Não foi possível processar o webhook agora.", retryable=True, retry_after_seconds=10)
    return jsonify(result), 200
