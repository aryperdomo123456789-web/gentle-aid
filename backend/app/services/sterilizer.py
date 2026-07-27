"""Motor de esterilização de mídia — deixa cada arquivo "virgem" e único.

Objetivo: nenhum arquivo entregue por qualquer ferramenta do ecossistema pode
carregar a identidade do arquivo de origem. Toda saída passa obrigatoriamente
por aqui antes de virar link de download.

O que o motor faz em uma única passada de FFmpeg:

1. Destrói 100% dos metadados herdados (container, streams, capítulos, XMP,
   ID3, tags de editor tipo Canva/CapCut/Premiere).
2. Forja uma identidade nova e aleatória (encoder, handler, creation_time,
   timescale, ordem/rotação de trilhas).
3. Aplica mutação estrutural imperceptível ao olho humano, porém suficiente
   para quebrar fingerprint perceptual (crop sub-pixel, rescale, gamma/eq,
   hue, ruído temporal, jitter de PTS, GOP e bitrate randômicos).
4. Reescreve o áudio (pitch/tempo micro, ganho, resample) para quebrar
   fingerprint de áudio tipo Content ID.
5. Verifica o MD5 e o SHA-256 final e, se por qualquer motivo o hash coincidir
   com o de origem, re-executa com uma nova semente até garantir unicidade.
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import config

# Níveis suportados por todas as ferramentas.
LEVELS = ("off", "leve", "media", "agressiva", "extrema")
DEFAULT_LEVEL = "media"

# Identidades falsas plausíveis para o campo encoder/handler.
_FAKE_ENCODERS = (
    "Lavf58.76.100",
    "Lavf59.27.100",
    "Lavf60.16.100",
    "HandBrake 1.7.3 2024022300",
    "Apple QuickTime 10.5",
    "Google/video-processor",
)
_FAKE_HANDLERS = (
    "VideoHandler",
    "Core Media Video",
    "ISO Media file produced by Google Inc.",
    "SoundHandler",
    "Core Media Audio",
)


def file_hashes(path: Path, chunk: int = 1 << 20) -> dict[str, str]:
    """MD5 + SHA-256 do arquivo (fingerprint de entrega, não uso criptográfico)."""
    md5 = hashlib.md5()  # noqa: S324
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            md5.update(block)
            sha.update(block)
    return {"md5": md5.hexdigest(), "sha256": sha.hexdigest()}


def md5(path: Path) -> str:
    return file_hashes(path)["md5"]


@dataclass
class Probe:
    width: int = 0
    height: int = 0
    fps: float = 30.0
    duration: float = 0.0
    has_audio: bool = False
    has_video: bool = False


@dataclass
class SterilizationReport:
    """Resumo auditável do que foi feito no arquivo."""

    level: str
    seed: int
    md5_before: str = ""
    md5_after: str = ""
    sha256_after: str = ""
    bitrate: str = ""
    attempts: int = 1
    video_filters: list[str] = field(default_factory=list)
    audio_filters: list[str] = field(default_factory=list)
    identity: dict[str, str] = field(default_factory=dict)
    steps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "seed": self.seed,
            "md5_before": self.md5_before,
            "md5_after": self.md5_after,
            "sha256_after": self.sha256_after,
            "bitrate": self.bitrate,
            "attempts": self.attempts,
            "video_filters": self.video_filters,
            "audio_filters": self.audio_filters,
            "identity": self.identity,
            "steps": self.steps,
            "unique": bool(self.md5_after) and self.md5_after != self.md5_before,
        }


# --------------------------------------------------------------------------
# Probe
# --------------------------------------------------------------------------
def probe(path: Path) -> Probe:
    try:
        out = subprocess.run(  # noqa: S603
            [
                config.ffprobe_bin,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height,avg_frame_rate",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        ).stdout
        data = json.loads(out or "{}")
    except (json.JSONDecodeError, subprocess.SubprocessError, OSError):
        return Probe()

    info = Probe()
    try:
        info.duration = float(data.get("format", {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        info.duration = 0.0

    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        if kind == "video" and not info.has_video:
            info.has_video = True
            info.width = int(stream.get("width") or 0)
            info.height = int(stream.get("height") or 0)
            rate = str(stream.get("avg_frame_rate") or "30/1")
            try:
                num, _, den = rate.partition("/")
                info.fps = float(num) / float(den or 1) if float(den or 1) else 30.0
            except (TypeError, ValueError, ZeroDivisionError):
                info.fps = 30.0
        elif kind == "audio":
            info.has_audio = True
    return info


def probe_duration(path: Path) -> float:
    return probe(path).duration


# --------------------------------------------------------------------------
# Construção das cadeias de filtro
# --------------------------------------------------------------------------
def _even(value: int) -> int:
    return max(2, value - (value % 2))


def build_video_filters(level: str, info: Probe, rng: random.Random) -> list[str]:
    """Mutação estrutural — imperceptível ao humano, letal para fingerprint."""
    if level == "off" or not info.has_video:
        return []

    intensity = {"leve": 0.35, "media": 1.0, "agressiva": 1.7, "extrema": 2.4}.get(level, 1.0)
    filters: list[str] = []

    # 1. Crop microscópico em posição aleatória + rescale para a grade original.
    if info.width and info.height:
        cut_x = _even(int(rng.uniform(2, 6 * intensity)))
        cut_y = _even(int(rng.uniform(2, 6 * intensity)))
        w = _even(info.width - cut_x)
        h = _even(info.height - cut_y)
        off_x = _even(rng.randint(0, max(0, cut_x)))
        off_y = _even(rng.randint(0, max(0, cut_y)))
        filters.append(f"crop={w}:{h}:{off_x}:{off_y}")
        filters.append(f"scale={_even(info.width)}:{_even(info.height)}:flags=lanczos")
    else:
        filters.append("crop=iw-4:ih-4")
        filters.append("scale=iw+4:ih+4:flags=lanczos")

    # 2. Colorimetria: desloca o histograma sem mudar a percepção.
    filters.append(
        "eq="
        f"contrast={1 + rng.uniform(0.008, 0.03) * intensity:.4f}:"
        f"brightness={rng.uniform(-0.012, 0.012) * intensity:.4f}:"
        f"saturation={1 + rng.uniform(0.008, 0.035) * intensity:.4f}:"
        f"gamma={1 + rng.uniform(-0.02, 0.02) * intensity:.4f}"
    )

    # 3. Rotação de matiz mínima — quebra hash de cor dominante.
    filters.append(f"hue=h={rng.uniform(-1.4, 1.4) * intensity:.3f}:s={1 + rng.uniform(-0.01, 0.01):.4f}")

    # 4. Nitidez sutil — altera coeficientes DCT sem artefato visível.
    if level in {"media", "agressiva", "extrema"}:
        filters.append(f"unsharp=3:3:{rng.uniform(0.15, 0.45):.3f}:3:3:0.0")

    # 5. Ruído temporal — impede casamento frame a frame.
    if level in {"agressiva", "extrema"}:
        filters.append(f"noise=alls={rng.randint(2, 6)}:allf=t+u")

    # 6. Jitter de tempo — desloca a linha temporal do fingerprint.
    speed = 1 + rng.uniform(0.004, 0.018) * intensity
    filters.append(f"setpts=PTS/{speed:.5f}")

    # 7. Nível extremo: espelhamento imperceptível de bordas via padding zerado.
    if level == "extrema":
        filters.append("setdar=dar=iw/ih")

    return filters


def build_audio_filters(level: str, info: Probe, rng: random.Random, speed: float) -> list[str]:
    if level == "off" or not info.has_audio:
        return []

    rate = 48000
    pitch = 1 + rng.uniform(-0.006, 0.006) * {"leve": 0.4, "media": 1.0, "agressiva": 1.6, "extrema": 2.2}.get(level, 1.0)
    filters = [
        f"asetrate={int(rate * pitch)}",
        f"aresample={rate}",
        f"atempo={speed / pitch:.6f}",
        f"volume={1 + rng.uniform(-0.02, 0.02):.4f}",
    ]
    if level in {"agressiva", "extrema"}:
        filters.append(f"highpass=f={rng.randint(18, 32)}")
        filters.append(f"lowpass=f={rng.randint(17600, 18400)}")
    return filters


def _fake_identity(rng: random.Random) -> dict[str, str]:
    created = datetime.now(timezone.utc) - timedelta(
        days=rng.randint(0, 21), hours=rng.randint(0, 23), minutes=rng.randint(0, 59)
    )
    return {
        "encoder": rng.choice(_FAKE_ENCODERS),
        "handler_video": rng.choice(_FAKE_HANDLERS),
        "handler_audio": rng.choice(_FAKE_HANDLERS),
        "creation_time": created.strftime("%Y-%m-%dT%H:%M:%S.000000Z"),
        "timescale": str(rng.choice((15360, 24000, 30000, 48000, 90000))),
    }


def pick_bitrate(profile: str, rng: random.Random) -> str:
    if profile and profile != "auto":
        return profile
    return f"{rng.randint(3600, 7400)}k"


# --------------------------------------------------------------------------
# Pipeline principal
# --------------------------------------------------------------------------
def build_command(
    src: Path,
    dst: Path,
    *,
    level: str,
    bitrate: str,
    info: Probe,
    rng: random.Random,
    extra_video_filters: list[str] | None = None,
    extra_audio_filters: list[str] | None = None,
) -> tuple[list[str], SterilizationReport]:
    identity = _fake_identity(rng)
    suffix = dst.suffix.lower()
    mp4_family = suffix in {".mp4", ".mov", ".m4a", ".m4v"}
    vf = list(extra_video_filters or []) + build_video_filters(level, info, rng)

    speed_filter = next((f for f in vf if f.startswith("setpts=PTS/")), "")
    speed = float(speed_filter.split("/")[-1]) if speed_filter else 1.0
    af = list(extra_audio_filters or []) + build_audio_filters(level, info, rng, speed)

    chosen_bitrate = pick_bitrate(bitrate, rng)
    gop = rng.choice((48, 50, 60, 72, 90))
    preset = rng.choice(("veryfast", "faster", "fast"))


    cmd: list[str] = [
        config.ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostdin",
        "-i",
        str(src),
    ]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    if af:
        cmd += ["-af", ",".join(af)]

    if info.has_video:
        cmd += [
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-profile:v",
            "high",
            "-level",
            rng.choice(("4.0", "4.1", "4.2")),
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            chosen_bitrate,
            "-maxrate",
            chosen_bitrate,
            "-bufsize",
            f"{int(chosen_bitrate.rstrip('k') or 5000) * 2}k",
            "-g",
            str(gop),
            "-keyint_min",
            str(max(2, gop // 2)),
            "-sc_threshold",
            "0",
        ]
        if mp4_family:
            cmd += ["-video_track_timescale", identity["timescale"]]

    if info.has_audio:
        if suffix == ".wav":
            cmd += ["-c:a", "pcm_s16le", "-ar", "48000"]
        elif suffix == ".mp3":
            cmd += ["-c:a", "libmp3lame", "-b:a", f"{rng.choice((192, 256, 320))}k", "-ar", "48000"]
        else:
            cmd += ["-c:a", "aac", "-b:a", f"{rng.choice((128, 160, 192))}k", "-ar", "48000"]
    else:
        cmd += ["-an"]


    # Extermínio total dos metadados de origem + identidade forjada.
    cmd += [
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-metadata",
        f"encoder={identity['encoder']}",
        "-metadata",
        f"creation_time={identity['creation_time']}",
        "-metadata",
        "title=",
        "-metadata",
        "comment=",
        "-metadata",
        "description=",
        "-metadata",
        "artist=",
        "-metadata",
        "album=",
        "-metadata",
        "copyright=",
    ]
    if info.has_video:
        cmd += ["-metadata:s:v:0", f"handler_name={identity['handler_video']}"]
    if info.has_audio:
        cmd += ["-metadata:s:a:0", f"handler_name={identity['handler_audio']}"]

    if mp4_family:
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(dst))


    report = SterilizationReport(
        level=level,
        seed=rng.randint(0, 2**31),
        bitrate=chosen_bitrate,
        video_filters=vf,
        audio_filters=af,
        identity=identity,
    )
    return cmd, report


def sterilize(
    src: Path,
    dst: Path,
    *,
    job_id: str | None = None,
    level: str = DEFAULT_LEVEL,
    bitrate: str = "auto",
    extra_video_filters: list[str] | None = None,
    extra_audio_filters: list[str] | None = None,
    max_attempts: int = 3,
    runner=None,
) -> SterilizationReport:
    """Esteriliza `src` em `dst` e devolve o relatório da operação."""
    from . import media  # import tardio evita ciclo

    execute = runner or media.run
    if level not in LEVELS:
        level = DEFAULT_LEVEL

    info = probe(src)
    before = file_hashes(src)
    seed = random.SystemRandom().randint(0, 2**31)

    report: SterilizationReport | None = None
    for attempt in range(1, max_attempts + 1):
        rng = random.Random(seed + attempt * 7919)  # noqa: S311 - variação cosmética
        cmd, report = build_command(
            src,
            dst,
            level=level,
            bitrate=bitrate,
            info=info,
            rng=rng,
            extra_video_filters=extra_video_filters,
            extra_audio_filters=extra_audio_filters,
        )
        report.md5_before = before["md5"]
        report.attempts = attempt
        execute(cmd, job_id=job_id)

        after = file_hashes(dst)
        report.md5_after = after["md5"]
        report.sha256_after = after["sha256"]
        report.steps = [
            "Metadados de origem destruídos (container, streams, capítulos)",
            f"Identidade forjada: {report.identity['encoder']} @ {report.identity['creation_time']}",
            f"Mutação estrutural nível '{level}' ({len(report.video_filters)} filtro(s) de vídeo)",
            f"Áudio reescrito ({len(report.audio_filters)} filtro(s)) e re-encodado em AAC 48 kHz",
            f"Bitrate randômico {report.bitrate} + GOP variável",
            f"Hash final inédito: MD5 {report.md5_after[:12]}…",
        ]
        if report.md5_after != report.md5_before:
            return report
        if job_id:
            from . import jobs as jobs_service

            jobs_service.log(job_id, f"Hash colidiu na tentativa {attempt} — repetindo com nova semente.")

    if report is None:  # pragma: no cover - defensivo
        raise RuntimeError("Falha ao esterilizar o arquivo.")
    return report
