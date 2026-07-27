"""Wrappers de FFmpeg/FFprobe e utilitários de mídia."""

from __future__ import annotations

import hashlib
import random
import shlex
import subprocess
from pathlib import Path

from ..config import config
from . import jobs


def md5(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.md5()  # noqa: S324 - fingerprint de arquivo, não uso criptográfico
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def run(cmd: list[str], job_id: str | None = None, timeout: int = 3600) -> str:
    """Executa um comando externo transmitindo stderr para o log do job."""
    if job_id:
        jobs.log(job_id, f"$ {' '.join(shlex.quote(c) for c in cmd)}")

    proc = subprocess.run(  # noqa: S603 - argumentos são construídos internamente
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = (proc.stderr or "") + (proc.stdout or "")
    if job_id:
        for line in output.strip().splitlines()[-25:]:
            jobs.log(job_id, line)
    if proc.returncode != 0:
        raise RuntimeError(f"Comando falhou ({proc.returncode}): {output.strip()[-500:]}")
    return output


def probe_duration(path: Path) -> float:
    out = run(
        [
            config.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    try:
        return float(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0.0


def mutation_filters(level: str) -> list[str]:
    """Filtros de vídeo para mutação estrutural (bypass de fingerprint)."""
    if level == "off":
        return []
    if level == "leve":
        return ["eq=contrast=1.01"]
    if level == "agressiva":
        return [
            "crop=iw*0.98:ih*0.98",
            "scale=iw/2*2:ih/2*2",
            "eq=contrast=1.04:saturation=1.06:brightness=0.01",
            "noise=alls=3:allf=t",
            "setpts=PTS/1.02",
        ]
    # média (default)
    return [
        "crop=iw*0.99:ih*0.99",
        "scale=iw/2*2:ih/2*2",
        "eq=contrast=1.02:saturation=1.03",
        "setpts=PTS/1.01",
    ]


def pick_bitrate(profile: str) -> str:
    if profile and profile != "auto":
        return profile
    return f"{random.randint(3800, 7200)}k"  # noqa: S311 - variação cosmética


def sanitize_video(
    src: Path,
    dst: Path,
    *,
    job_id: str,
    mutation: str = "media",
    bitrate: str = "auto",
    strip_metadata: bool = True,
    audio_speed: float | None = None,
) -> Path:
    """Re-encode H.264/AAC + limpeza de metadados + micro-mutação temporal."""
    vf = mutation_filters(mutation)
    af: list[str] = []
    if mutation in {"media", "agressiva"}:
        af.append("atempo=1.01" if mutation == "media" else "atempo=1.02")
    if audio_speed:
        af.append(f"atempo={audio_speed}")

    cmd = [config.ffmpeg_bin, "-y", "-hide_banner", "-i", str(src)]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    if af:
        cmd += ["-af", ",".join(af)]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        pick_bitrate(bitrate),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-movflags",
        "+faststart",
    ]
    if strip_metadata:
        cmd += [
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:v",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            "-metadata",
            "encoder=",
        ]
    cmd.append(str(dst))

    run(cmd, job_id=job_id)
    return dst


def burn_subtitles(src: Path, srt: Path, dst: Path, *, job_id: str, style: str, position: str) -> Path:
    styles = {
        "viral": "FontName=DejaVu Sans,Fontsize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=4,Shadow=1",
        "karaoke": "FontName=DejaVu Sans,Fontsize=22,Bold=1,PrimaryColour=&H0000F5FF,OutlineColour=&H00000000,Outline=3",
        "clean": "FontName=DejaVu Sans,Fontsize=18,PrimaryColour=&H00FFFFFF,Outline=1,Shadow=0",
        "neon": "FontName=DejaVu Sans,Fontsize=22,Bold=1,PrimaryColour=&H00F65C8B,OutlineColour=&H00200020,Outline=3,Shadow=2",
    }
    alignment = {"bottom": 2, "center": 5, "top": 8}.get(position, 2)
    force_style = f"{styles.get(style, styles['viral'])},Alignment={alignment}"
    escaped = str(srt).replace("\\", "/").replace(":", r"\:")

    run(
        [
            config.ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-i",
            str(src),
            "-vf",
            f"subtitles='{escaped}':force_style='{force_style}'",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(dst),
        ],
        job_id=job_id,
    )
    return dst
