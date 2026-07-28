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
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class Provider:
    label: str
    url: str
    key: str
    kind: str
    base_url: str | None = None


# --------------------------------------------------------------------------- #
# Provedores
# --------------------------------------------------------------------------- #
def _providers() -> list[Provider]:
    """(rótulo, url, chave) na ordem de preferência."""
    out: list[Provider] = []
    groq = api_keys.get_key("groq")
    if groq:
        out.append(Provider("Groq · whisper-large-v3", GROQ_URL, groq, "openai"))
    whisper = api_keys.get_key("whisper")
    if whisper:
        base = os.environ.get("WHISPER_API_BASE", "https://api.whisper-api.com").rstrip("/")
        if "whisper-api.com" in base:
            out.append(Provider("Whisper API", f"{base}/transcribe", whisper, "whisper_api", base))
        else:
            out.append(Provider("Whisper compatível", f"{base}/audio/transcriptions", whisper, "openai", base))
    return out


def available() -> bool:
    return bool(_providers())


def missing_key_message() -> str:
    return (
        "A dublagem precisa ouvir o vídeo: cadastre a chave Groq (ou Whisper) em /apis "
        "para liberar a transcrição com timestamps. O Whisper pode usar Whisper API "
        "ou um endpoint compatível com OpenAI via WHISPER_API_BASE."
    )


# --------------------------------------------------------------------------- #
# HTTP multipart
# --------------------------------------------------------------------------- #
def _multipart(fields: dict[str, object], file_path: Path) -> tuple[bytes, str]:
    boundary = f"----viraldub{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, raw in fields.items():
        values = raw if isinstance(raw, (list, tuple)) else [raw]
        for value in values:
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


def _srt_seconds(value: str) -> float:
    match = re.match(r"^\s*(\d+):(\d+):(\d+)[,\.](\d+)\s*$", value)
    if not match:
        return 0.0
    hours, minutes, seconds, millis = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def _payload_from_srt(text: str, *, duration: float, language: str | None = None) -> dict:
    segments: list[dict[str, object]] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        if "-->" in lines[0]:
            time_line = lines[0]
            body = lines[1:]
        elif len(lines) >= 3 and "-->" in lines[1]:
            time_line = lines[1]
            body = lines[2:]
        else:
            continue
        left, _, right = time_line.partition("-->")
        start = _srt_seconds(left.strip())
        end = _srt_seconds(right.strip().split()[0])
        if end <= start:
            end = start + 0.5
        text_value = " ".join(body).strip()
        if text_value:
            segments.append({"start": start, "end": end, "text": text_value})
    if not segments:
        text_value = text.strip()
        if text_value:
            segments = [{"start": 0.0, "end": max(0.5, duration), "text": text_value}]
    return {
        "language": language or "",
        "text": " ".join(str(seg["text"]) for seg in segments).strip(),
        "segments": segments,
    }


def _post_openai(provider: Provider, file_path: Path, language: str | None, *, words: bool = False) -> dict:
    fields: dict[str, object] = {
        "model": GROQ_MODEL if "groq" in provider.url else "whisper-1",
        "response_format": "verbose_json",
        "temperature": "0",
    }
    if words:
        fields["timestamp_granularities[]"] = ["segment", "word"]
    if language:
        fields["language"] = language
    body, content_type = _multipart(fields, file_path)

    req = urllib.request.Request(provider.url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {provider.key}")
    req.add_header("Content-Type", content_type)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "EcossistemaViral/1.0")
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:  # noqa: S310 - host do provedor
            return json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        if exc.code in (401, 403):
            raise TranscribeError(
                f"Chave de transcrição recusada ({exc.code}). Abra /apis, clique em 'Testar' na Groq "
                f"(ou Whisper) e cadastre uma chave válida — o teste agora envia um áudio real. "
                f"Detalhe do provedor: {detail}"
            ) from exc
        raise TranscribeError(f"Transcrição recusada ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise TranscribeError(f"Falha de rede na transcrição: {exc.reason}") from exc


def _post_whisper_api(provider: Provider, file_path: Path, language: str | None, *, duration: float) -> dict:
    fields: dict[str, object] = {
        "format": "srt",
        "model_size": "large",
    }
    if language:
        fields["language"] = language
    body, content_type = _multipart(fields, file_path)

    req = urllib.request.Request(provider.url, data=body, method="POST")
    req.add_header("X-API-Key", provider.key)
    req.add_header("Content-Type", content_type)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "EcossistemaViral/1.0")
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:  # noqa: S310 - host do provedor
            payload = json.loads(resp.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        if exc.code in (401, 403):
            raise TranscribeError(
                f"Chave de transcrição recusada ({exc.code}). Abra /apis, clique em 'Testar' na Groq "
                f"(ou Whisper) e cadastre uma chave válida — o teste agora envia um áudio real. "
                f"Detalhe do provedor: {detail}"
            ) from exc
        raise TranscribeError(f"Transcrição recusada ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise TranscribeError(f"Falha de rede na transcrição: {exc.reason}") from exc

    task_id = str(payload.get("task_id") or "").strip()
    status = str(payload.get("status") or "").lower()
    if task_id and status in {"queued", "processing", "pending"}:
        status_url = f"{provider.base_url.rstrip('/')}/status/{urllib.parse.quote(task_id)}"
        deadline = time.time() + 900
        while True:
            if time.time() > deadline:
                raise TranscribeError("Tempo esgotado aguardando a conclusão da transcrição no Whisper API.")
            time.sleep(2.0)
            req = urllib.request.Request(status_url, method="GET")
            req.add_header("X-API-Key", provider.key)
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "EcossistemaViral/1.0")
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - host do provedor
                    payload = json.loads(resp.read().decode("utf-8", "ignore"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                raise TranscribeError(f"Transcrição do Whisper API recusada ({exc.code}): {detail}") from exc
            except urllib.error.URLError as exc:
                raise TranscribeError(f"Falha de rede na transcrição: {exc.reason}") from exc

            status = str(payload.get("status") or "").lower()
            if status in {"completed", "complete", "done"}:
                break
            if status in {"failed", "error", "canceled", "cancelled"}:
                detail = json.dumps(payload, ensure_ascii=False)[:500]
                raise TranscribeError(f"Transcrição do Whisper API falhou: {detail}")

    result = payload.get("result")
    if isinstance(result, str):
        return _payload_from_srt(result, duration=duration, language=payload.get("language") or language)
    if isinstance(result, dict):
        if "segments" in result:
            return result
        if isinstance(result.get("text"), str):
            return _payload_from_srt(str(result.get("text")), duration=duration, language=payload.get("language") or language)
    if isinstance(payload.get("text"), str):
        return _payload_from_srt(str(payload.get("text")), duration=duration, language=payload.get("language") or language)
    return {"language": payload.get("language") or language or "", "segments": [], "text": ""}


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


def _words_from(payload: dict, offset: float) -> list[WordStamp]:
    out: list[WordStamp] = []
    for item in payload.get("words") or []:
        text = str(item.get("word") or item.get("text") or "").strip()
        if not text:
            continue
        try:
            start = float(item.get("start", 0.0)) + offset
            end = float(item.get("end", 0.0)) + offset
        except (TypeError, ValueError):
            continue
        if end <= start:
            end = start + 0.18
        out.append(WordStamp(start=start, end=end, text=text))
    out.sort(key=lambda w: w.start)
    return out


def _segments_from(payload: dict, offset: float) -> list[Segment]:
    raw = payload.get("segments") or []
    all_words = _words_from(payload, offset)
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
        inline = _words_from(item, offset)
        if not inline and all_words:
            inline = [w for w in all_words if w.start >= start - 0.05 and w.start < end + 0.05]
        out.append(Segment(start=start, end=end, text=text, words=inline))
    if not out:
        text = (payload.get("text") or "").strip()
        if text:
            end = all_words[-1].end if all_words else offset + 5.0
            out.append(Segment(start=offset, end=end, text=text, words=all_words))
    return out


def transcribe(
    src: Path, *, job_id: str, language: str | None = None, word_timestamps: bool = False
) -> tuple[list[Segment], str]:
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
            jobs.check_cancelled(job_id)
            offset = index * CHUNK_SECONDS
            piece = _extract_mp3(
                src, work / f"stt_{index:04d}.mp3",
                start=offset, duration=min(CHUNK_SECONDS, duration - offset), job_id=None,
            )
            payload: dict | None = None
            for provider in providers:
                try:
                    if provider.kind == "whisper_api":
                        payload = _post_whisper_api(provider, piece, language, duration=min(CHUNK_SECONDS, duration - offset))
                    else:
                        payload = _post_openai(provider, piece, language, words=word_timestamps)
                    if index == 0:
                        jobs.log(job_id, f"Transcrição via {provider.label}")
                    break
                except TranscribeError as exc:
                    last_error = exc
                    jobs.log(job_id, f"{provider.label} falhou: {exc}")
                    if word_timestamps:
                        try:
                            if provider.kind == "whisper_api":
                                payload = _post_whisper_api(
                                    provider, piece, language, duration=min(CHUNK_SECONDS, duration - offset)
                                )
                            else:
                                payload = _post_openai(provider, piece, language, words=False)
                            jobs.log(job_id, f"{provider.label} sem timestamps por palavra — usando fallback.")
                            break
                        except TranscribeError:
                            pass
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
