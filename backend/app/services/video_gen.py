"""Gerador de Vídeo IA — do prompt ao MP4 esterilizado.

Pipeline (tudo dentro do padrão de jobs/rastro do ecossistema):

  1. storyboard  → cenas com narração + descrição visual (`storyboard.plan`)
  2. narração    → Edge TTS grátis (+ persona do Voice Forge, opcional)
  3. visual      → `visuals.fetch` (imagem IA / b-roll / upload / premium)
  4. clipe       → Ken Burns (zoompan) na imagem ou corte do b-roll, com áudio
  5. montagem    → concat dos clipes + trilha opcional em ducking
  6. legenda     → ASS animado do Estúdio de Legendas queimado na esterilização
  7. entrega     → `deliver` com hash inédito e metadados zerados
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from ..config import config
from . import captions, edge_tts, jobs, media, visuals, voice_forge
from .delivery import deliver
from .validation import output_path

ASPECTS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}

FPS = 30


def dimensions(aspect: str) -> tuple[int, int]:
    return ASPECTS.get(aspect, ASPECTS["9:16"])


def _narrate(text: str, dst: Path, *, voice: str, persona_id: str, job_id: str, rate: int) -> Path:
    raw = dst.with_name(dst.stem + "_raw.wav")
    edge_tts.synthesize(text, raw, voice=voice, job_id=job_id, rate_percent=rate)
    persona = voice_forge.get(persona_id) if persona_id else None
    if persona is None:
        raw.replace(dst)
        return dst
    chain = voice_forge.filter_chain(persona)
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw), "-af", ",".join(chain),
            "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=None,
    )
    raw.unlink(missing_ok=True)
    return dst


def _clip_from_image(
    image: Path, audio: Path, dst: Path, *, seconds: float, width: int, height: int, seed: int
) -> None:
    """Ken Burns: zoom/pan lento para uma foto virar plano de vídeo."""
    frames = max(2, int(seconds * FPS))
    rnd = random.Random(seed)
    zoom_in = rnd.random() < 0.6
    zoom_expr = (
        f"min(zoom+{0.0012 + rnd.random() * 0.0008:.4f},1.28)"
        if zoom_in
        else f"max(1.28-on*{0.0012 + rnd.random() * 0.0008:.4f},1.0)"
    )
    xdir = rnd.choice(["iw/2-(iw/zoom/2)", "iw/2-(iw/zoom/2)+(on/%d)*40" % frames])
    ydir = rnd.choice(["ih/2-(ih/zoom/2)", "ih/2-(ih/zoom/2)-(on/%d)*40" % frames])
    vf = (
        f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
        f"crop={width * 2}:{height * 2},"
        f"zoompan=z='{zoom_expr}':x='{xdir}':y='{ydir}':d={frames}:s={width}x{height}:fps={FPS},"
        f"format=yuv420p"
    )
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(image), "-i", str(audio),
            "-filter_complex", f"[0:v]{vf}[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", f"{seconds:.3f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", str(dst),
        ],
        job_id=None,
    )


def _clip_from_video(
    source: Path, audio: Path, dst: Path, *, seconds: float, width: int, height: int
) -> None:
    """B-roll cortado, enquadrado e mudo (a narração manda no áudio)."""
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps={FPS},format=yuv420p"
    )
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", str(source), "-i", str(audio),
            "-filter_complex", f"[0:v]{vf}[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", f"{seconds:.3f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", str(dst),
        ],
        job_id=None,
    )


def _concat(parts: list[Path], dst: Path, workdir: Path, job_id: str) -> None:
    listing = workdir / "concat.txt"
    listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            str(dst),
        ],
        job_id=job_id,
    )


def _mix_music(video: Path, music: Path, dst: Path, *, volume: float, job_id: str) -> None:
    """Trilha em ducking: a música abaixa sozinha quando a narração entra."""
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


def generate(
    job_id: str,
    *,
    scenes: list[dict[str, Any]],
    mode: str,
    aspect: str,
    look_suffix: str,
    voice: str,
    persona_id: str,
    rate_percent: int,
    uploads: list[Path],
    music: Path | None,
    music_volume: float,
    caption_preset: str | None,
    caption_position: str,
    mutation: str,
) -> dict[str, Any]:
    """Executa o pipeline completo e entrega o MP4 esterilizado."""
    width, height = dimensions(aspect)
    workdir = config.tool_dir("studio") / job_id / "_work"
    workdir.mkdir(parents=True, exist_ok=True)
    seed = random.SystemRandom().randint(1, 10**6)

    clips: list[Path] = []
    timeline: list[dict[str, Any]] = []
    sources: dict[str, int] = {}
    cursor = 0.0

    for index, scene in enumerate(scenes):
        jobs.check_cancelled(job_id)
        progress = 10 + int(60 * index / max(1, len(scenes)))
        jobs.stage(
            job_id,
            "cena",
            f"Cena {index + 1}/{len(scenes)} · narrando e buscando o visual.",
            progress=progress,
        )

        audio = workdir / f"voz_{index:03d}.wav"
        _narrate(
            scene["narration"], audio, voice=voice, persona_id=persona_id, job_id=job_id, rate=rate_percent
        )
        seconds = max(1.2, media.probe_duration(audio) + 0.25)

        try:
            asset = visuals.fetch(
                scene,
                mode=mode,
                workdir=workdir,
                index=index,
                width=width,
                height=height,
                look_suffix=look_suffix,
                uploads=uploads,
                job_id=job_id,
                seed=seed,
            )
        except visuals.VisualError as exc:
            jobs.log(
                job_id,
                f"Cena {index + 1}: sem mídia externa ({exc}) — usando cartão sólido.",
                level="warn",
                stage="visual",
            )
            asset = visuals.solid_card(
                workdir / f"scene_{index:03d}.png",
                width=width,
                height=height,
                ffmpeg=config.ffmpeg_bin,
                runner=media.run,
            )

        sources[asset.source] = sources.get(asset.source, 0) + 1
        clip = workdir / f"clip_{index:03d}.mp4"
        if asset.kind == "video":
            _clip_from_video(asset.path, audio, clip, seconds=seconds, width=width, height=height)
        else:
            _clip_from_image(
                asset.path, audio, clip, seconds=seconds, width=width, height=height, seed=seed + index
            )
        clips.append(clip)
        timeline.append(
            {
                "index": index,
                "start": round(cursor, 2),
                "end": round(cursor + seconds, 2),
                "seconds": round(seconds, 2),
                "source": asset.source,
                "narration": scene["narration"],
            }
        )
        cursor += seconds

    if not clips:
        raise RuntimeError("Nenhuma cena foi montada — revise o storyboard.")

    jobs.check_cancelled(job_id)
    jobs.stage(job_id, "montando", f"Juntando {len(clips)} cena(s) — {cursor:.1f}s de vídeo.", progress=74)
    montage = workdir / "montagem.mp4"
    _concat(clips, montage, workdir, job_id)

    if music and music.exists():
        jobs.stage(job_id, "trilha", "Aplicando trilha com ducking sobre a narração.", progress=80)
        with_music = workdir / "com_trilha.mp4"
        _mix_music(montage, music, with_music, volume=music_volume, job_id=job_id)
        montage = with_music

    ass_path: Path | None = None
    if caption_preset:
        jobs.stage(job_id, "legendando", f"Gerando legenda animada no preset '{caption_preset}'.", progress=86)
        lines: list[captions.Line] = []
        for item in timeline:
            words = captions.spread_words(item["narration"], item["start"], item["end"])
            lines.extend(captions.group_words(words, max_words=4))
        if lines:
            ass_path = output_path("studio", job_id, ".ass")
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
            jobs.update(job_id, caption_lines=len(lines))

    jobs.check_cancelled(job_id)
    dst = output_path("studio", job_id, "_video.mp4")
    jobs.stage(job_id, "esterilizando", "Renderização final + esterilização do arquivo.", progress=92)
    report = (
        media.burn_ass(montage, ass_path, dst, job_id=job_id, mutation=mutation)
        if ass_path
        else media.sterilize(montage, dst, job_id=job_id, level=mutation)
    )

    for leftover in sorted(workdir.rglob("*"), reverse=True):
        if leftover.is_file():
            leftover.unlink(missing_ok=True)
    workdir.rmdir()

    summary = ", ".join(f"{count}× {name}" for name, count in sources.items()) or "sem fonte externa"
    jobs.update(job_id, timeline=timeline, visual_sources=sources, total_seconds=round(cursor, 1))
    return deliver(
        job_id,
        dst,
        report,
        message=f"Vídeo gerado com {len(clips)} cena(s) ({summary}) e entregue virgem.",
        extra={"scenes": len(clips)},
    )
