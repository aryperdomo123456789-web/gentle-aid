"""Ferramenta nova — transcrição de vídeo por URL em texto puro."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request

from ..services import ingest, jobs, media, transcribe
from ..services.validation import ValidationError, clean_text, output_path, public_url

bp = Blueprint("transcribe_video", __name__, url_prefix="/api/transcribe")


def _segments_to_text(segments: list[transcribe.Segment]) -> str:
    parts: list[str] = []
    for segment in segments:
        text = " ".join(segment.text.split())
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


@bp.post("/run")
def run_job():
    try:
        source_url = clean_text(request.form.get("url"), max_length=500, field="url")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    if not ingest.is_supported_url(source_url):
        return jsonify(error="Cole um link público de vídeo válido."), 400
    if not transcribe.available():
        return jsonify(error=transcribe.missing_key_message()), 400

    job = jobs.create_job("transcribe", meta={"url": source_url})
    jobs.submit(job["job_id"], lambda jid: _work(jid, source_url))
    return jsonify(job), 202


def _work(job_id: str, source_url: str) -> None:
    src: Path | None = None
    try:
        jobs.stage(job_id, "baixando", "Baixando o vídeo para extrair a fala.", progress=12)
        src = ingest.resolve_source(None, source_url, job_id)
        info = media.probe(src)
        if not info.has_audio:
            raise RuntimeError("Esse vídeo não tem trilha de áudio para transcrever.")

        jobs.stage(job_id, "transcrevendo", "Escutando o áudio e convertendo em texto.", progress=28)
        segments, detected = transcribe.transcribe(src, job_id=job_id)
        transcript_text = _segments_to_text(segments)
        if not transcript_text:
            raise RuntimeError("Não foi possível montar a transcrição do vídeo.")

        dst = output_path("transcribe", job_id, ".txt")
        dst.write_text(transcript_text + "\n", encoding="utf-8")
        jobs.register_artifact(job_id, dst, "transcript")

        download = public_url(dst)
        summary = (
            f"Transcrição concluída · {len(segments)} trecho(s)"
            f"{f' · idioma {detected}' if detected else ''}."
        )
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        jobs.update(
            job_id,
            status="done",
            stage="entregue",
            progress=100,
            message=summary,
            download_url=download,
            filename=dst.name,
            size_bytes=dst.stat().st_size,
            transcript_text=transcript_text,
            transcript_language=detected or None,
            outputs=[{"download_url": download, "filename": dst.name, "url": download}],
            finished_at=finished_at,
        )
        jobs.audit("delivered", job_id, "transcribe", f"{dst.name} txt")
        jobs.log(job_id, f"Transcrição salva em {dst.name}", level="audit", stage="entregue")
    finally:
        if src is not None:
            src.unlink(missing_ok=True)
