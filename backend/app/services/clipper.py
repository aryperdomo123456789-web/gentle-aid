"""Fábrica de Cortes — vídeo longo entra, cortes verticais legendados saem.

Pipeline (mesmo padrão de jobs/rastro/esterilização do resto do ecossistema):

  1. fonte      → upload ou link (`ingest.resolve_source`)
  2. escuta     → transcrição com timestamp por palavra (`transcribe`)
  3. inteligência → melhores momentos por nicho (`highlights.find` + IA opcional)
  4. corte      → recorte exato + reenquadramento 9:16 (crop ou fundo desfocado)
  5. trilha     → música de fundo com ducking sobre a voz (opcional)
  6. legenda    → ASS animado do Estúdio de Legendas, queimado na esterilização
  7. entrega    → cada corte vira artefato; o melhor vira o download principal
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import config
from . import captions, highlights, jobs, media, transcribe
from .delivery import deliver
from .validation import output_path

ASPECTS: dict[str, tuple[int, int] | None] = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "original": None,
}
FRAMES = ("crop", "blur", "pad")
FPS = 30


def _video_filter(width: int, height: int, frame: str) -> str:
    """Reenquadramento: corte central, fundo desfocado (TikTok) ou barras pretas."""
    if frame == "blur":
        return (
            f"[0:v]split=2[bg][fg];"
            f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},gblur=sigma=28,eq=brightness=-0.06[bgb];"
            f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,fps={FPS},format=yuv420p[v]"
        )
    if frame == "pad":
        return (
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,fps={FPS},format=yuv420p[v]"
        )
    return (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={FPS},format=yuv420p[v]"
    )



def _cut(
    src: Path,
    dst: Path,
    *,
    start: float,
    seconds: float,
    size: tuple[int, int] | None,
    frame: str,
    voice_volume: float,
    job_id: str,
) -> None:
    """Recorte exato (seek preciso) já reenquadrado e normalizado."""
    cmd = [
        config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{max(0.0, start):.3f}", "-i", str(src), "-t", f"{seconds:.3f}",
    ]
    if size:
        width, height = size
        cmd += ["-filter_complex", _video_filter(width, height, frame), "-map", "[v]"]
    else:
        cmd += ["-vf", f"fps={FPS},format=yuv420p", "-map", "0:v:0"]
    cmd += [
        "-map", "0:a:0?",
        "-af", f"volume={voice_volume:.2f},aresample=48000,loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(dst),
    ]
    media.run(cmd, job_id=job_id)


def _mix_music(video: Path, music: Path, dst: Path, *, volume: float, job_id: str) -> None:
    """Trilha em ducking: abaixa sozinha quando a voz entra."""
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video), "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            f"[1:a]volume={volume:.2f},aresample=48000[m];"
            "[m][0:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=350[duck];"
            "[0:a][duck]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(dst),
        ],
        job_id=job_id,
    )


class _Seg:
    """Segmento deslocado para o tempo local do corte (0 = início do corte)."""

    def __init__(self, start: float, end: float, text: str, words: list[Any]):
        self.start = start
        self.end = end
        self.text = text
        self.words = words


class _Word:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


def _local_segments(segments: list[Any], start: float, end: float) -> list[_Seg]:
    out: list[_Seg] = []
    for seg in segments:
        s = float(getattr(seg, "start", 0.0) or 0.0)
        e = float(getattr(seg, "end", 0.0) or 0.0)
        if e <= start or s >= end:
            continue
        text = str(getattr(seg, "text", "") or "").strip()
        if not text:
            continue
        words: list[_Word] = []
        for w in getattr(seg, "words", None) or []:
            ws = float(getattr(w, "start", 0.0) or 0.0)
            we = float(getattr(w, "end", 0.0) or 0.0) or ws + 0.25
            token = str(getattr(w, "text", "") or "").strip()
            if not token or we <= start or ws >= end:
                continue
            words.append(_Word(max(0.0, ws - start), max(0.06, we - start), token))
        out.append(
            _Seg(
                max(0.0, s - start),
                max(0.2, min(end, e) - start),
                text,
                words,
            )
        )
    return out


def generate(
    job_id: str,
    *,
    src: Path,
    niche_id: str,
    min_seconds: float,
    max_seconds: float,
    max_clips: int,
    aspect: str,
    frame: str,
    caption_preset: str | None,
    caption_position: str,
    words_per_line: int,
    language: str | None,
    music: Path | None,
    music_volume: float,
    voice_volume: float,
    use_ai: bool,
    mutation: str,
    manual_segments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Roda o pipeline inteiro e entrega todos os cortes do vídeo."""
    size = ASPECTS.get(aspect, ASPECTS["9:16"])
    workdir = config.tool_dir("clips") / job_id / "_work"
    workdir.mkdir(parents=True, exist_ok=True)

    duration = max(1.0, media.probe_duration(src))
    jobs.update(job_id, source_duration=round(duration, 1))

    manual = list(manual_segments or [])
    segments: list[Any] = []
    detected: str | None = None
    provider = None

    # Modo manual sem legenda não precisa ouvir o vídeo: corta na régua e pronto.
    needs_transcript = bool(caption_preset) or not manual
    if needs_transcript:
        jobs.stage(job_id, "ouvindo", f"Transcrevendo {duration / 60:.1f} min de vídeo.", progress=8)
        segments, detected = transcribe.transcribe(
            src, job_id=job_id, language=language, word_timestamps=True
        )
        jobs.log(
            job_id, f"Idioma detectado: {detected or 'desconhecido'} · {len(segments)} trecho(s)."
        )

    if manual:
        clips = []
        for position, item in enumerate(manual):
            start = max(0.0, min(float(item.get("start") or 0.0), duration - 1.0))
            end = min(duration, max(start + 1.0, float(item.get("end") or 0.0)))
            clips.append(
                {
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "title": str(item.get("title") or f"Corte manual {position + 1}").strip(),
                    "score": None,
                    "reasons": ["Corte definido manualmente na régua de edição."],
                }
            )
        jobs.stage(
            job_id, "editando", f"{len(clips)} corte(s) manuais na régua.", progress=50
        )
    else:
        jobs.stage(job_id, "analisando", "Procurando os melhores momentos do vídeo.", progress=48)
        clips = highlights.find(
            segments,
            niche_id=niche_id,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            max_clips=max_clips,
            total_duration=duration,
        )
        if not clips:
            raise RuntimeError(
                "Nenhum trecho com fala suficiente para o intervalo pedido — "
                "reduza a duração mínima do corte."
            )

        if use_ai and highlights.llm_available():
            jobs.stage(
                job_id, "curadoria", "IA especialista rankeando e batizando os cortes.", progress=54
            )
            refined = highlights.refine(clips, niche_id=niche_id, language="português do Brasil")
            clips = refined["clips"]
            provider = refined.get("provider")

        if provider:
            jobs.log(job_id, f"Curadoria por IA via {provider}.")
        else:
            jobs.log(job_id, "Curadoria por IA indisponível — mantendo ranking heurístico.", level="warn")

    jobs.update(job_id, clips_planned=len(clips), ai_provider=provider)
    jobs.log(job_id, f"{len(clips)} corte(s) selecionado(s) no nicho '{niche_id}'.")

    width, height = size if size else (1080, 1920)
    delivered: list[dict[str, Any]] = []
    best: tuple[float, Path, dict[str, Any], Any] | None = None

    for position, clip in enumerate(clips):
        jobs.check_cancelled(job_id)
        seconds = max(2.0, float(clip["end"]) - float(clip["start"]))
        jobs.stage(
            job_id,
            "cortando",
            f"Corte {position + 1}/{len(clips)} · {seconds:.0f}s — {clip['title']}",
            progress=56 + int(38 * position / max(1, len(clips))),
        )

        raw = workdir / f"corte_{position:02d}.mp4"
        _cut(
            src,
            raw,
            start=float(clip["start"]),
            seconds=seconds,
            size=size,
            frame=frame,
            voice_volume=voice_volume,
            job_id=job_id,
        )

        if music and music.exists():
            mixed = workdir / f"corte_{position:02d}_trilha.mp4"
            _mix_music(raw, music, mixed, volume=music_volume, job_id=job_id)
            raw.unlink(missing_ok=True)
            raw = mixed

        ass_path: Path | None = None
        if caption_preset:
            lines = captions.lines_from_segments(
                _local_segments(segments, float(clip["start"]), float(clip["end"])),
                max_words=words_per_line,
            )
            if lines:
                ass_path = output_path("clips", job_id, f"_corte{position:02d}.ass")
                ass_path.write_text(
                    captions.build_ass(
                        lines,
                        preset_id=caption_preset,
                        video_width=width,
                        video_height=height,
                        position=caption_position,
                        animation="auto",
                    ),
                    encoding="utf-8",
                )
                jobs.register_artifact(job_id, ass_path, "captions")

        dst = output_path("clips", job_id, f"_corte{position:02d}.mp4")
        report = (
            media.burn_ass(raw, ass_path, dst, job_id=job_id, mutation=mutation)
            if ass_path
            else media.sterilize(raw, dst, job_id=job_id, level=mutation)
        )
        raw.unlink(missing_ok=True)
        jobs.register_artifact(job_id, dst, "output")

        entry = {
            "index": position,
            "title": clip["title"],
            "start": clip["start"],
            "end": clip["end"],
            "seconds": round(seconds, 1),
            "score": clip.get("ai_score") or clip.get("score"),
            "ai_score": clip.get("ai_score"),
            "reasons": clip.get("reasons") or [],
            "filename": dst.name,
            "download_url": f"/downloads/{dst.relative_to(config.storage_dir).as_posix()}",
            "md5_after": report.md5_after,
            "size_bytes": dst.stat().st_size if dst.exists() else 0,
        }
        delivered.append(entry)
        jobs.update(job_id, clips=delivered, clips_done=len(delivered))

        rank = float(clip.get("ai_score") or clip.get("score") or 0)
        if best is None or rank > best[0]:
            best = (rank, dst, entry, report)

    for leftover in sorted(workdir.rglob("*"), reverse=True):
        if leftover.is_file():
            leftover.unlink(missing_ok=True)
    workdir.rmdir()

    assert best is not None
    _, best_path, best_entry, best_report = best
    jobs.update(job_id, clips=delivered, transcript_language=detected or None)
    return deliver(
        job_id,
        best_path,
        best_report,
        message=(
            f"{len(delivered)} corte(s) prontos e esterilizados. "
            f"Destaque: “{best_entry['title']}” ({best_entry['seconds']:.0f}s)."
        ),
        extra={"clips": delivered, "clips_total": len(delivered)},
    )
