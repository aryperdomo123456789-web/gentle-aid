"""Helpers compartilhados entre blueprints."""

from __future__ import annotations

import re
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..config import config

SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg"}


class ValidationError(ValueError):
    """Erro de validação de entrada (vira HTTP 400)."""


def save_upload(file: FileStorage | None, job_id: str, allowed: set[str]) -> Path:
    if file is None or not file.filename:
        raise ValidationError("Nenhum arquivo enviado.")

    name = secure_filename(file.filename)
    ext = Path(name).suffix.lower()
    if ext not in allowed:
        raise ValidationError(f"Extensão '{ext or 'desconhecida'}' não permitida.")

    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = config.uploads_dir / f"{job_id}_src{ext}"
    file.save(dest)
    if dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise ValidationError("Arquivo vazio.")
    return dest


def output_path(tool: str, job_id: str, suffix: str) -> Path:
    out_dir = config.tool_dir(tool) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{job_id}{suffix}"


def public_url(path: Path) -> str:
    """Converte um caminho absoluto no storage em URL relativa de download."""
    rel = path.relative_to(config.storage_dir)
    return f"/downloads/{rel.as_posix()}"


def clean_text(value: str | None, *, max_length: int, field: str) -> str:
    text = (value or "").strip()
    if len(text) > max_length:
        raise ValidationError(f"Campo '{field}' excede {max_length} caracteres.")
    return text


YOUTUBE_RE = re.compile(r"^https?://(www\.)?(youtube\.com|youtu\.be|m\.youtube\.com)/", re.I)
TIKTOK_RE = re.compile(r"^https?://([\w-]+\.)?tiktok\.com/", re.I)
