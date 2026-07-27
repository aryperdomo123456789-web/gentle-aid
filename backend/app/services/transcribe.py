"""Transcrição com timestamps — a "escuta" do motor de dublagem.

Fluxo: áudio → Whisper large v3 (Groq, rápido e barato) → segmentos com
`start`, `end` e `text`. Áudios longos são fatiados em blocos de 10 minutos e
os timestamps de cada bloco são deslocados, então 10 segundos ou 3 horas usam o
mesmo caminho.

Fallback: qualquer endpoint compatível com a OpenAI (`WHISPER_API_BASE`) usando
a chave do provedor `whisper` do cofre.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..config import config
from . import api_keys, jobs, media

# Blocos de 10 min: seguros para o limite de upload (25 MB) mesmo em MP3 64 kbps.
CHUNK_SECONDS = 600
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3"


class TranscribeError(RuntimeError):
    """Erro de transcrição com mensagem pronta para o operador."""


@dataclass
class WordStamp:
    start: float
    end: float
    text: str

    def dict(self) -> dict[str, object]:
        return {"start": round(self.start, 3), "end": round(self.end, 3), "text": self.text}


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list["WordStamp"] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(0.05, self.end - self.start)

    def dict(self) -> dict[str, object]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
            "words": [w.dict() for w in self.words],
        }



# --------------------------------------------------------------------------- #
# Provedores
# --------------------------------------------------------------------------- #
def _providers() -> list[tuple[str, str, str]]:
    """(rótulo, url, chave) na ordem de preferência."""
    out: list[tuple[str, str, str]] = []
    groq = api_keys.get_key("groq")
    if groq:
        out.append(("Groq · whisper-large-v3", GROQ_URL, groq))
    whisper = api_keys.get_key("whisper")
    if whisper:
        base = os.environ.get("WHISPER_API_BASE", "https://api.openai.com/v1").rstrip("/")
        out.append(("Whisper compatível", f"{base}/audio/transcriptions", whisper))
    return out


def available() -> bool:
    return bool(_providers())


def missing_key_message() -> str:
    return (
        "A dublagem precisa ouvir o vídeo: cadastre a chave Groq (ou Whisper) em /apis "
        "para liberar a transcrição com timestamps."
    )


# --------------------------------------------------------------------------- #
# HTTP multipart
# --------------------------------------------------------------------------- #
def _multipart(fields: dict[str, str], file_path: Path) -> tuple[bytes, str]:
    boundary = f"----viraldub{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{file_path.name}\"\r\nContent-Type: audio/mpeg\r\n\r\n".encode()
    )
    parts.append(file_path.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _post(url: str, key: str, file_path: Path, language: str | None) -> dict:
    fields = {
        "model": GROQ_MODEL if "groq" in url else "whisper-1",
        "response_format": "verbose_json",
        "temperature": "0",
    }
    if language:
        fields["language"] = language
    body, content_type = _multipart(fields, file_path)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:  # noqa: S310 - host do provedor
            return json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise TranscribeError(f"Transcrição recusada ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise TranscribeError(f"Falha de rede na transcrição: {exc.reason}") from exc


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def _extract_mp3(src: Path, dst: Path, *, start: float, duration: float, job_id: str | None) -> Path:
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(src),
            "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(dst),
        ],
        job_id=job_id,
    )
    return dst


def _segments_from(payload: dict, offset: float) -> list[Segment]:
    raw = payload.get("segments") or []
    out: list[Segment] = []
    for item in raw:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        try:
            start = float(item.get("start", 0.0)) + offset
            end = float(item.get("end", 0.0)) + offset
        except (TypeError, ValueError):
            continue
        if end <= start:
            end = start + 0.4
        out.append(Segment(start=start, end=end, text=text))
    if not out:
        text = (payload.get("text") or "").strip()
        if text:
            out.append(Segment(start=offset, end=offset + 5.0, text=text))
    return out


def transcribe(src: Path, *, job_id: str, language: str | None = None) -> tuple[list[Segment], str]:
    """Devolve (segmentos, idioma detectado)."""
    providers = _providers()
    if not providers:
        raise TranscribeError(missing_key_message())

    duration = max(0.1, media.probe_duration(src))
    work = src.parent / f"{job_id}_stt"
    work.mkdir(parents=True, exist_ok=True)

    blocks = max(1, int((duration + CHUNK_SECONDS - 1) // CHUNK_SECONDS))
    jobs.log(job_id, f"Ouvindo o áudio original · {duration:.1f}s em {blocks} bloco(s)")

    segments: list[Segment] = []
    detected = language or ""
    last_error: Exception | None = None
    try:
        for index in range(blocks):
            offset = index * CHUNK_SECONDS
            piece = _extract_mp3(
                src, work / f"stt_{index:04d}.mp3",
                start=offset, duration=min(CHUNK_SECONDS, duration - offset), job_id=None,
            )
            payload: dict | None = None
            for label, url, key in providers:
                try:
                    payload = _post(url, key, piece, language)
                    if index == 0:
                        jobs.log(job_id, f"Transcrição via {label}")
                    break
                except TranscribeError as exc:
                    last_error = exc
                    jobs.log(job_id, f"{label} falhou: {exc}")
            piece.unlink(missing_ok=True)
            if payload is None:
                raise TranscribeError(str(last_error) if last_error else "Nenhum provedor de transcrição respondeu.")
            detected = detected or (payload.get("language") or "")
            segments.extend(_segments_from(payload, offset))
            jobs.update(job_id, progress=min(45, 12 + int(30 * (index + 1) / blocks)))
    finally:
        for leftover in work.glob("*"):
            leftover.unlink(missing_ok=True)
        work.rmdir()

    if not segments:
        raise TranscribeError("Não foi possível extrair fala desse vídeo — o áudio parece não ter narração.")

    segments.sort(key=lambda s: s.start)
    jobs.log(job_id, f"{len(segments)} trecho(s) de fala mapeados · idioma {detected or 'auto'}")
    return segments, detected
