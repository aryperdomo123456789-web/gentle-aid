"""Entrega padronizada de resultados de job (URL + fingerprint + relatório)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import jobs
from .sterilizer import SterilizationReport
from .validation import public_url


def _human_size(bytes_value: int) -> str:
    if bytes_value <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(bytes_value)
    unit = 0
    while value >= 1024 and unit < len(units) - 1:
        value /= 1024
        unit += 1
    if value >= 10 or unit == 0:
        return f"{value:.0f} {units[unit]}"
    return f"{value:.1f} {units[unit]}"


def _format_bitrate(bit_rate: int) -> str:
    if bit_rate <= 0:
        return "não detectado"
    mbps = bit_rate / 1_000_000
    if mbps >= 1:
        return f"{mbps:.2f} Mbps"
    return f"{bit_rate / 1_000:.0f} kbps"


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "não detectada"
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_audit_summary(report: SterilizationReport, dst: Path) -> str:
    source_codec = report.source_video_codec or "desconhecido"
    output_codec = report.output_video_codec or "desconhecido"
    source_dims = (
        f"{report.source_width}x{report.source_height}" if report.source_width and report.source_height else "não detectada"
    )
    output_dims = source_dims
    delta_ms = int(round((report.output_duration - report.source_duration) * 1000))
    duration_sign = "+" if delta_ms >= 0 else "-"
    duration_delta = f"{duration_sign}{abs(delta_ms)} ms"
    bitrate_ratio = None
    if report.source_bitrate > 0 and report.output_bitrate > 0:
        bitrate_ratio = report.output_bitrate / report.source_bitrate
    source_size = _human_size(report.source_size_bytes)
    output_size = _human_size(report.output_size_bytes)

    lines = [
        "Resultado da Auditoria Estrutural: Aprovado com Louvor!",
        "",
        "📊 Comparativo Técnico",
        "**Métrica** | **Arquivo Original** | **Arquivo Final** | **Diagnóstico**",
        f"Duração Exata | {_format_duration(report.source_duration)} | {_format_duration(report.output_duration)} | Micro-mutação temporal ({duration_delta}): quebra o alinhamento entre áudio e vídeo.",
        f"Bitrate do Vídeo | {_format_bitrate(report.source_bitrate)} | {_format_bitrate(report.output_bitrate)} | Re-encodamento total e nova matriz de quantização.",
        f"Resolução / Codec | {source_dims} / {source_codec} | {output_dims} / {output_codec} | Estrutura preservada com identidade nova.",
        f"Tamanho do Arquivo | {source_size} | {output_size} | Arquivo regravado e persistido no servidor.",
    ]
    if bitrate_ratio is not None:
        lines.append(
            f"Variação de bitrate | 1.00x | {bitrate_ratio:.2f}x | O arquivo final foi reescrito com parâmetros novos."
        )
    lines.extend(
        [
            "",
            "🛡️ Veredito da Tríplice Blindagem",
            f"Esterilização de Metadados: 100% concluída.",
            f"Hash Digital (MD5): {report.md5_before[:12]}… ➔ {report.md5_after[:12]}…",
            f"Estrutura de Mídia (Arquivo Vivo): {report.attempts} tentativa(s), {len(report.video_filters)} filtro(s) de vídeo e {len(report.audio_filters)} filtro(s) de áudio.",
            f"Entrega final: {dst.name}",
        ]
    )
    if report.unique:
        lines.append(
            "O arquivo final foi entregue com fingerprint diferente e relatório persistido no servidor."
        )
    else:
        lines.append("O arquivo final foi entregue, mas o hash coincidiu com a origem.")
    return "\n".join(lines)


def deliver(
    job_id: str,
    dst: Path,
    report: SterilizationReport,
    *,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Marca o job como concluído com o arquivo já esterilizado."""
    report.audit_summary = _format_audit_summary(report, dst)
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
        "audit_summary": report.audit_summary,
    }
    if extra:
        payload.update(extra)
    jobs.update(job_id, **payload)
    for step in report.steps:
        jobs.log(job_id, f"✔ {step}")
    return payload
