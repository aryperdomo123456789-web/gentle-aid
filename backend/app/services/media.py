"""Wrappers de FFmpeg/FFprobe e utilitários de mídia.

Toda saída de vídeo do ecossistema passa por `sterilizer.sterilize`, garantindo
arquivo "virgem": zero metadados herdados, identidade forjada, mutação
estrutural e hash inédito.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from ..config import config
from . import jobs
from .sterilizer import (  # re-export para os blueprints
    DEFAULT_LEVEL,
    LEVELS,
    SterilizationReport,
    file_hashes,
    md5,
    probe,
    probe_duration,
    sterilize,
)

__all__ = [
    "DEFAULT_LEVEL",
    "LEVELS",
    "SterilizationReport",
    "burn_subtitles",
    "file_hashes",
    "md5",
    "probe",
    "probe_duration",
    "run",
    "sanitize_video",
    "sterilize",
    "subtitle_filter",
]


def run(cmd: list[str], job_id: str | None = None, timeout: int = 3600) -> str:
    """Executa um comando externo transmitindo stderr para o log do job."""
    if job_id:
        jobs.log(job_id, f"$ {' '.join(shlex.quote(c) for c in cmd)}")

    try:
        proc = subprocess.run(  # noqa: S603 - argumentos construídos internamente
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Binário não encontrado: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Tempo limite de {timeout}s excedido em {cmd[0]}.") from exc

    output = (proc.stderr or "") + (proc.stdout or "")
    if job_id:
        for line in output.strip().splitlines()[-25:]:
            jobs.log(job_id, line)
    if proc.returncode != 0:
        raise RuntimeError(f"Comando falhou ({proc.returncode}): {output.strip()[-500:]}")
    return output


def sanitize_video(
    src: Path,
    dst: Path,
    *,
    job_id: str,
    mutation: str = DEFAULT_LEVEL,
    bitrate: str = "auto",
    **_legacy,
) -> SterilizationReport:
    """Esteriliza um vídeo (compatibilidade com a assinatura antiga)."""
    return sterilize(src, dst, job_id=job_id, level=mutation, bitrate=bitrate)


SUBTITLE_STYLES = {
    "viral": "FontName=DejaVu Sans,Fontsize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=4,Shadow=1",
    "karaoke": "FontName=DejaVu Sans,Fontsize=22,Bold=1,PrimaryColour=&H0000F5FF,OutlineColour=&H00000000,Outline=3",
    "clean": "FontName=DejaVu Sans,Fontsize=18,PrimaryColour=&H00FFFFFF,Outline=1,Shadow=0",
    "neon": "FontName=DejaVu Sans,Fontsize=22,Bold=1,PrimaryColour=&H00F65C8B,OutlineColour=&H00200020,Outline=3,Shadow=2",
}
SUBTITLE_ALIGNMENT = {"bottom": 2, "center": 5, "top": 8}


def subtitle_filter(srt: Path, *, style: str, position: str) -> str:
    """Monta o filtro `subtitles` já escapado para uso dentro do -vf."""
    alignment = SUBTITLE_ALIGNMENT.get(position, 2)
    force_style = f"{SUBTITLE_STYLES.get(style, SUBTITLE_STYLES['viral'])},Alignment={alignment}"
    escaped = str(srt).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return f"subtitles='{escaped}':force_style='{force_style}'"


def burn_subtitles(
    src: Path,
    srt: Path,
    dst: Path,
    *,
    job_id: str,
    style: str,
    position: str,
    mutation: str = DEFAULT_LEVEL,
) -> SterilizationReport:
    """Queima legendas e esteriliza no MESMO encode (uma única passada)."""
    return sterilize(
        src,
        dst,
        job_id=job_id,
        level=mutation,
        extra_video_filters=[subtitle_filter(srt, style=style, position=position)],
    )
