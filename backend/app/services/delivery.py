"""Entrega padronizada de resultados de job (URL + fingerprint + relatório)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import jobs
from .sterilizer import SterilizationReport
from .validation import public_url


def deliver(
    job_id: str,
    dst: Path,
    report: SterilizationReport,
    *,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Marca o job como concluído com o arquivo já esterilizado."""
    payload: dict[str, Any] = {
        "status": "done",
        "progress": 100,
        "message": message,
        "download_url": public_url(dst),
        "filename": dst.name,
        "size_bytes": dst.stat().st_size if dst.exists() else 0,
        "md5_before": report.md5_before,
        "md5_after": report.md5_after,
        "sha256_after": report.sha256_after,
        "sterilization": report.as_dict(),
    }
    if extra:
        payload.update(extra)
    jobs.update(job_id, **payload)
    for step in report.steps:
        jobs.log(job_id, f"✔ {step}")
    return payload
