"""Exportação de segmentos de transcrição para formatos públicos."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

OUTPUT_FORMATS = {"srt", "vtt", "json", "json_verbose", "text"}

_FORMAT_EXTENSIONS = {
    "srt": "srt",
    "vtt": "vtt",
    "json": "json",
    "json_verbose": "json_verbose",
    "text": "txt",
}

_MIME_TYPES = {
    "srt": "application/x-subrip; charset=utf-8",
    "vtt": "text/vtt; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "json_verbose": "application/json; charset=utf-8",
    "text": "text/plain; charset=utf-8",
}


def extension_for(output_format: str) -> str:
    normalized = str(output_format or "").strip().lower()
    if normalized not in OUTPUT_FORMATS:
        raise ValueError(f"Formato de exportação não suportado: {output_format}")
    return _FORMAT_EXTENSIONS[normalized]


def mime_type(output_format: str) -> str:
    normalized = str(output_format or "").strip().lower()
    if normalized not in OUTPUT_FORMATS:
        raise ValueError(f"Formato de exportação não suportado: {output_format}")
    return _MIME_TYPES[normalized]


def media_mime_type(extension: str) -> str:
    normalized = str(extension or "").strip().lower().lstrip(".")
    return {
        "mp4": "video/mp4",
        "m4a": "audio/mp4",
        "mov": "video/quicktime",
        "mkv": "video/x-matroska",
        "webm": "video/webm",
    }.get(normalized, "application/octet-stream")


def _round_seconds(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return round(default, 3)


def _word_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "dict"):
        item = item.dict()
    if not isinstance(item, Mapping):
        return {"start": 0.0, "end": 0.0, "text": str(item or "")}
    return {
        "start": _round_seconds(item.get("start")),
        "end": _round_seconds(item.get("end")),
        "text": str(item.get("text") or item.get("word") or "").strip(),
    }


def segment_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "dict"):
        item = item.dict()
    if not isinstance(item, Mapping):
        item = {}
    start = _round_seconds(item.get("start"))
    end = _round_seconds(item.get("end"), start + 0.4)
    if end <= start:
        end = round(start + 0.4, 3)
    return {
        "start": start,
        "end": end,
        "text": str(item.get("text") or "").strip(),
        "words": [_word_dict(word) for word in (item.get("words") or [])],
    }


def normalized_segments(segments: Iterable[Any]) -> list[dict[str, Any]]:
    output = [segment_dict(item) for item in segments]
    return [item for item in output if item["text"]]


def verbose_payload(
    segments: Iterable[Any],
    *,
    language: str | None = None,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    normalized = normalized_segments(segments)
    if duration_seconds is None:
        duration_seconds = max((item["end"] for item in normalized), default=0.0)
    return {
        "object": "transcription",
        "language": language or None,
        "duration_seconds": _round_seconds(duration_seconds),
        "text": " ".join(item["text"] for item in normalized).strip(),
        "segments": normalized,
    }


def _timestamp(seconds: float, *, vtt: bool) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def render_payload(payload: Mapping[str, Any], output_format: str) -> str:
    normalized = str(output_format or "").strip().lower()
    if normalized not in OUTPUT_FORMATS:
        raise ValueError(f"Formato de exportação não suportado: {output_format}")

    segments = normalized_segments(payload.get("segments") or [])
    if normalized == "json":
        return json.dumps(
            {"language": payload.get("language"), "segments": segments},
            ensure_ascii=False,
            indent=2,
        ) + "\n"
    if normalized == "json_verbose":
        value = dict(payload)
        value["segments"] = segments
        value.setdefault("object", "transcription")
        value.setdefault("text", " ".join(item["text"] for item in segments).strip())
        return json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if normalized == "text":
        return "\n".join(item["text"] for item in segments) + ("\n" if segments else "")

    vtt = normalized == "vtt"
    lines = ["WEBVTT", ""] if vtt else []
    for index, segment in enumerate(segments, start=1):
        start = _timestamp(segment["start"], vtt=vtt)
        end = _timestamp(max(segment["end"], segment["start"] + 0.05), vtt=vtt)
        if not vtt:
            lines.append(str(index))
        lines.extend([f"{start} --> {end}", segment["text"], ""])
    return "\n".join(lines)


def render_segments(
    segments: Iterable[Any],
    output_format: str,
    *,
    language: str | None = None,
    duration_seconds: float | None = None,
) -> str:
    return render_payload(
        verbose_payload(segments, language=language, duration_seconds=duration_seconds),
        output_format,
    )
