"""Recorte de mídia e legendas relativas para o Viral Clip Engine."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from ..config import config
from . import jobs, media, transcription_exports

MIN_CLIP_SECONDS = 1.0
MAX_CLIP_SECONDS = 90.0


class ClipValidationError(ValueError):
    pass


def validate_window(start: Any, end: Any, duration: Any) -> tuple[float, float, float]:
    try:
        start_value = float(start)
        end_value = float(end)
        duration_value = float(duration)
    except (TypeError, ValueError) as exc:
        raise ClipValidationError("start_seconds e end_seconds devem ser números.") from exc
    if not all(math.isfinite(value) for value in (start_value, end_value, duration_value)):
        raise ClipValidationError("A janela do clipe contém um número inválido.")
    duration_value = max(0.0, duration_value)
    if start_value < 0 or end_value <= start_value:
        raise ClipValidationError("A janela do clipe deve ter início e fim válidos.")
    clip_duration = end_value - start_value
    if clip_duration < MIN_CLIP_SECONDS or clip_duration > MAX_CLIP_SECONDS:
        raise ClipValidationError("A duração do clipe deve ficar entre 1 e 90 segundos.")
    if end_value > duration_value + 0.25:
        raise ClipValidationError("O fim do clipe ultrapassa a duração da transcrição.")
    return round(start_value, 3), round(min(end_value, duration_value), 3), round(duration_value, 3)


def _relative_word(word: Mapping[str, Any], start: float, end: float) -> dict[str, Any] | None:
    try:
        word_start = float(word.get("start", 0.0))
        word_end = float(word.get("end", word_start))
    except (TypeError, ValueError):
        return None
    if word_end <= start or word_start >= end:
        return None
    relative_start = max(word_start, start) - start
    relative_end = min(word_end, end) - start
    if relative_end <= relative_start:
        relative_end = relative_start + 0.08
    return {
        "start": round(max(0.0, relative_start), 3),
        "end": round(max(0.0, relative_end), 3),
        "text": str(word.get("text") or word.get("word") or "").strip(),
    }


def relative_segments(
    segments: list[Mapping[str, Any]],
    start: float,
    end: float,
) -> list[dict[str, Any]]:
    """Recorta segmentos/palavras e subtrai o início do clipe."""
    output: list[dict[str, Any]] = []
    for segment in segments:
        try:
            segment_start = float(segment.get("start", 0.0))
            segment_end = float(segment.get("end", segment_start))
        except (TypeError, ValueError):
            continue
        if segment_end <= start or segment_start >= end:
            continue
        clipped_start = max(segment_start, start)
        clipped_end = min(segment_end, end)
        if clipped_end <= clipped_start:
            continue
        words = [
            relative
            for word in (segment.get("words") or [])
            if isinstance(word, Mapping)
            for relative in [_relative_word(word, start, end)]
            if relative and relative.get("text")
        ]
        output.append(
            {
                "start": round(clipped_start - start, 3),
                "end": round(max(clipped_end - start, clipped_start - start + 0.08), 3),
                "text": str(segment.get("text") or "").strip(),
                "words": words,
            }
        )
    output.sort(key=lambda item: (item["start"], item["end"]))
    return output


def clip_payload(
    transcription: Mapping[str, Any],
    start: float,
    end: float,
    *,
    insight: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    segments = relative_segments(
        [item for item in (transcription.get("segments") or []) if isinstance(item, Mapping)],
        start,
        end,
    )
    payload: dict[str, Any] = {
        "object": "viral_clip",
        "duration_seconds": round(end - start, 3),
        "source_start_seconds": round(start, 3),
        "source_end_seconds": round(end, 3),
        "language": transcription.get("language"),
        "text": " ".join(item["text"] for item in segments).strip(),
        "segments": segments,
    }
    if insight:
        payload["insight"] = {
            key: insight[key]
            for key in ("retention_score", "suggested_title", "initial_hook", "summary", "reasons")
            if key in insight
        }
    return payload


def source_in_storage(source: Path) -> Path:
    try:
        candidate = source.resolve()
        root = config.storage_dir.resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise ClipValidationError("A mídia-fonte não está disponível no storage protegido.")
        return candidate
    except (OSError, RuntimeError, ValueError) as exc:
        raise ClipValidationError("A mídia-fonte não está disponível no storage protegido.") from exc


def media_output_path(parent_job_id: str, clip_id: str, source: Path) -> Path:
    folder = config.tool_dir("viral-clips") / parent_job_id
    folder.mkdir(parents=True, exist_ok=True)
    suffix = ".mp4" if source.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"} else ".m4a"
    return folder / f"{clip_id}{suffix}"


def caption_output_path(parent_job_id: str, clip_id: str, extension: str) -> Path:
    folder = config.tool_dir("viral-clips") / parent_job_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{clip_id}.{extension}"


def slice_media(source: Path, destination: Path, *, start: float, end: float, job_id: str) -> Path:
    source = source_in_storage(source)
    duration = max(0.1, end - start)
    is_video = source.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
    if is_video:
        command = [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source),
            "-map", "0:v:0?", "-map", "0:a:0?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(destination),
        ]
    else:
        command = [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source),
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "128k", str(destination),
        ]
    media.run(command, job_id=job_id, timeout=20 * 60)
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("O clipe não foi gerado.")
    return destination


def render_captions(payload: Mapping[str, Any], extension: str) -> str:
    output_format = "vtt" if extension == "vtt" else "srt"
    return transcription_exports.render_payload(payload, output_format)
