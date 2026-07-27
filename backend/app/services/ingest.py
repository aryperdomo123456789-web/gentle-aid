"""Ingestão de mídia por URL — ponte entre o fluxo de pesquisa e as esteiras.

Todas as ferramentas aceitam upload **ou** uma URL vinda dos cards de
descoberta. Aqui a URL vira um arquivo local pronto para o FFmpeg.
"""

from __future__ import annotations

from pathlib import Path

from ..config import config
from . import jobs, media
from .validation import ValidationError


def is_supported_url(url: str) -> bool:
    return bool(url) and url.startswith(("http://", "https://")) and len(url) <= 500


def download_source(url: str, job_id: str) -> Path:
    """Baixa o vídeo da URL para a pasta de uploads e devolve o caminho."""
    if not is_supported_url(url):
        raise ValidationError("URL inválida.")

    config.uploads_dir.mkdir(parents=True, exist_ok=True)
    dest = config.uploads_dir / f"{job_id}_src.mp4"
    jobs.log(job_id, f"Baixando mídia de {url}")
    media.run(
        [
            config.ytdlp_bin,
            "-f",
            "b[ext=mp4]/b",
            "--no-playlist",
            "--merge-output-format",
            "mp4",
            "-o",
            str(dest),
            url,
        ],
        job_id=job_id,
    )
    if not dest.exists() or dest.stat().st_size == 0:
        raise ValidationError("Não foi possível baixar o vídeo dessa URL.")
    jobs.update(
        job_id,
        source_kind="download",
        source_label=url,
        source_path=str(dest),
        source_url=url,
    )
    jobs.register_artifact(job_id, dest, "input")
    return dest


def resolve_source(src: Path | None, source_url: str | None, job_id: str) -> Path:
    """Devolve o arquivo local, baixando da URL quando não houve upload."""
    if src is not None:
        return src
    if source_url:
        return download_source(source_url, job_id)
    raise ValidationError("Envie um arquivo ou selecione um vídeo na pesquisa.")
