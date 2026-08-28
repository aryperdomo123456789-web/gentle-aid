"""Ferramenta nova — transcrição de vídeo por URL em texto puro."""

from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ..config import config
from ..services import ingest, jobs, media, transcribe
from ..services.validation import YOUTUBE_RE, ValidationError, clean_text, output_path, public_url

bp = Blueprint("transcribe_video", __name__, url_prefix="/api/transcribe")


def _segments_to_text(segments: list[transcribe.Segment]) -> str:
    parts: list[str] = []
    for segment in segments:
        text = " ".join(segment.text.split())
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _is_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_RE.match(url))


def _download_youtube_source(url: str, job_id: str) -> Path:
    config_dir = config.uploads_dir
    config_dir.mkdir(parents=True, exist_ok=True)
    dest = config_dir / f"{job_id}_src.mp4"
    jobs.log(job_id, "Baixando mídia com o cliente Android do YouTube.")
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "format": "bv*+ba/best",
        "merge_output_format": "mp4",
        "outtmpl": str(config_dir / f"{job_id}_src.%(ext)s"),
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except DownloadError as exc:
        raise RuntimeError(str(exc)) from exc

    if dest.exists() and dest.stat().st_size > 0:
        jobs.update(
            job_id,
            source_kind="download",
            source_label=url,
            source_path=str(dest),
            source_url=url,
        )
        jobs.register_artifact(job_id, dest, "input")
        return dest

    candidates = sorted(
        (p for p in config_dir.glob(f"{job_id}_src.*") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        latest = candidates[0]
        if latest != dest:
            latest.replace(dest)
        jobs.update(
            job_id,
            source_kind="download",
            source_label=url,
            source_path=str(dest),
            source_url=url,
        )
        jobs.register_artifact(job_id, dest, "input")
        return dest

    raise RuntimeError("Não foi possível baixar o vídeo pelo YouTube.")


def _segments_from_caption_text(text: str, *, duration: float, language: str | None) -> list[transcribe.Segment]:
    payload = transcribe._payload_from_srt(text, duration=duration, language=language)
    segments: list[transcribe.Segment] = []
    for raw in payload.get("segments") or []:
        try:
            start = float(raw.get("start", 0.0))
            end = float(raw.get("end", 0.0))
        except (TypeError, ValueError):
            continue
        text_value = str(raw.get("text") or "").strip()
        if not text_value:
            continue
        segments.append(transcribe.Segment(start=start, end=end, text=text_value))
    return segments


def _fetch_caption_segments(url: str, job_id: str) -> tuple[list[transcribe.Segment], str]:
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    duration = float(info.get("duration") or 1.0)
    caption_maps = [
        ("subtitles", info.get("subtitles") or {}),
        ("automatic_captions", info.get("automatic_captions") or {}),
    ]
    preferred_langs = ["pt-BR", "pt", "pt-PT", "en", "en-US", "en-GB"]
    for _, captions in caption_maps:
        langs = list(captions.keys())
        ordered = [lang for lang in preferred_langs if lang in captions]
        ordered.extend(lang for lang in langs if lang not in ordered)
        for lang in ordered:
            entries = captions.get(lang) or []
            for entry in entries:
                if str(entry.get("ext") or "").lower() not in {"vtt", "srt"}:
                    continue
                caption_url = str(entry.get("url") or "").strip()
                if not caption_url:
                    continue
                jobs.log(job_id, f"Usando legenda automática do YouTube em {lang}.")
                req = urllib.request.Request(
                    caption_url,
                    headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - origem do provedor
                    text = resp.read().decode("utf-8", "ignore")
                segments = _segments_from_caption_text(text, duration=duration, language=lang)
                if segments:
                    return segments, lang
    raise RuntimeError("Este vídeo não expõe legenda automática aproveitável no YouTube.")


def _transcribe_youtube(job_id: str, source_url: str) -> tuple[list[transcribe.Segment], str]:
    src: Path | None = None
    download_error: Exception | None = None
    try:
        jobs.stage(job_id, "baixando", "Baixando o vídeo com o cliente Android do YouTube.", progress=12)
        src = _download_youtube_source(source_url, job_id)
        info = media.probe(src)
        if not info.has_audio:
            raise RuntimeError("Esse vídeo não tem trilha de áudio para transcrever.")
        jobs.stage(job_id, "transcrevendo", "Escutando o áudio e convertendo em texto.", progress=28)
        return transcribe.transcribe(src, job_id=job_id)
    except Exception as exc:  # fallback controlado para a trilha de captions
        download_error = exc
        jobs.log(job_id, f"Fluxo de áudio falhou: {exc}", level="error")
        jobs.stage(job_id, "transcrevendo", "Áudio indisponível; lendo legendas automáticas do YouTube.", progress=28)
        try:
            return _fetch_caption_segments(source_url, job_id)
        except Exception as caption_exc:
            raise RuntimeError(
                f"Não foi possível transcrever este vídeo. Tentativa por áudio: {download_error}. "
                f"Tentativa por legenda automática: {caption_exc}"
            ) from caption_exc
    finally:
        if src is not None:
            src.unlink(missing_ok=True)


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
    segments: list[transcribe.Segment]
    detected: str
    if _is_youtube_url(source_url):
        segments, detected = _transcribe_youtube(job_id, source_url)
    else:
        src: Path | None = None
        try:
            jobs.stage(job_id, "baixando", "Baixando o vídeo para extrair a fala.", progress=12)
            src = ingest.resolve_source(None, source_url, job_id)
            info = media.probe(src)
            if not info.has_audio:
                raise RuntimeError("Esse vídeo não tem trilha de áudio para transcrever.")

            jobs.stage(job_id, "transcrevendo", "Escutando o áudio e convertendo em texto.", progress=28)
            segments, detected = transcribe.transcribe(src, job_id=job_id)
        finally:
            if src is not None:
                src.unlink(missing_ok=True)

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
