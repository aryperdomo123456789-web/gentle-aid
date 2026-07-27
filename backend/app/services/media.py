"""Wrappers de FFmpeg/FFprobe e utilitários de mídia.

Toda saída de vídeo do ecossistema passa por `sterilizer.sterilize`, garantindo
arquivo "virgem": zero metadados herdados, identidade forjada, mutação
estrutural e hash inédito.
"""

from __future__ import annotations

import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

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


def run(
    cmd: list[str],
    job_id: str | None = None,
    timeout: int = 4 * 3600,
    line_callback: Callable[[str], None] | None = None,
) -> str:
    """Executa um comando externo com log ao vivo no painel."""
    if job_id:
        jobs.log(job_id, f"$ {' '.join(shlex.quote(c) for c in cmd)}")

    try:
        proc = subprocess.Popen(  # noqa: S603 - argumentos construídos internamente
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Binário não encontrado: {cmd[0]}") from exc

    output: list[str] = []
    finished = threading.Event()

    def reader() -> None:
        stream = proc.stdout
        if stream is None:
            finished.set()
            return
        try:
            for raw in iter(stream.readline, ""):
                line = raw.rstrip()
                if not line:
                    continue
                output.append(line)
                if job_id:
                    jobs.log(job_id, line)
                if line_callback:
                    try:
                        line_callback(line)
                    except Exception:
                        continue
        finally:
            finished.set()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    started = time.monotonic()
    cancel_event = jobs.cancel_event(job_id) if job_id else None
    while True:
        if cancel_event and cancel_event.is_set():
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            thread.join(timeout=5)
            raise jobs.JobCancelled("Processamento cancelado pelo operador.")
        code = proc.poll()
        if code is not None:
            break
        if timeout is not None and (time.monotonic() - started) > timeout:
            proc.kill()
            thread.join(timeout=5)
            raise RuntimeError(f"Tempo limite de {timeout}s excedido em {cmd[0]}.")
        time.sleep(0.25)

    thread.join(timeout=5)
    if proc.stdout:
        proc.stdout.close()

    output_text = "\n".join(output).strip()
    if code != 0:
        tail = output_text[-500:] if output_text else ""
        raise RuntimeError(f"Comando falhou ({code}): {tail}")
    return output_text


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


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def subtitle_filter(srt: Path, *, style: str, position: str) -> str:
    """Monta o filtro `subtitles` já escapado para uso dentro do -vf."""
    alignment = SUBTITLE_ALIGNMENT.get(position, 2)
    force_style = f"{SUBTITLE_STYLES.get(style, SUBTITLE_STYLES['viral'])},Alignment={alignment}"
    return f"subtitles='{_escape_filter_path(srt)}':force_style='{force_style}'"


def ass_filter(ass: Path) -> str:
    """Filtro `ass` — mantém todas as tags de animação do estúdio de legendas."""
    return f"ass='{_escape_filter_path(ass)}'"


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


def burn_ass(
    src: Path,
    ass: Path,
    dst: Path,
    *,
    job_id: str,
    mutation: str = DEFAULT_LEVEL,
) -> SterilizationReport:
    """Queima um ASS animado e esteriliza na mesma passada."""
    return sterilize(
        src,
        dst,
        job_id=job_id,
        level=mutation,
        extra_video_filters=[ass_filter(ass)],
    )

