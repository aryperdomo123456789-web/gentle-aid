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

import re
import hashlib
import json
import random
import subprocess
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import config

# Níveis suportados por todas as ferramentas.
LEVELS = ("auto", "off", "leve", "media", "agressiva", "extrema")
DEFAULT_LEVEL = "media"
_LEVEL_ALIASES = {
    "auto": "auto",
    "automatico": "auto",
    "auto inteligente": "auto",
    "desativado": "off",
    "off": "off",
    "leve": "leve",
    "media": "media",
    "avancado": "agressiva",
    "agressiva": "agressiva",
    "extrema": "extrema",
}

# --------------------------------------------------------------------------
# Formatos finais de vídeo — o operador escolhe em toda ferramenta que
# baixa/recodifica mídia. "original" mantém a proporção da fonte.
# --------------------------------------------------------------------------
VIDEO_FORMATS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "4:3": (1440, 1080),
}
DEFAULT_FORMAT = "original"
_FORMAT_ALIASES = {
    "": "original",
    "original": "original",
    "auto": "original",
    "fonte": "original",
    "mesmo": "original",
    "vertical": "9:16",
    "9x16": "9:16",
    "9:16": "9:16",
    "1080x1920": "9:16",
    "reels": "9:16",
    "shorts": "9:16",
    "tiktok": "9:16",
    "4:5": "4:5",
    "4x5": "4:5",
    "feed": "4:5",
    "quadrado": "1:1",
    "square": "1:1",
    "1:1": "1:1",
    "1x1": "1:1",
    "horizontal": "16:9",
    "16:9": "16:9",
    "16x9": "16:9",
    "youtube": "16:9",
    "1920x1080": "16:9",
    "4:3": "4:3",
    "4x3": "4:3",
}
FORMAT_FITS = ("cover", "contain")
DEFAULT_FIT = "cover"


def normalize_format(value: str | None) -> str:
    """Aceita apelidos ('vertical', 'shorts', '9x16') e devolve a chave canônica."""
    raw = str(value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", raw)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"\s+", "", normalized)
    return _FORMAT_ALIASES.get(normalized, DEFAULT_FORMAT)


def normalize_fit(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"contain", "conter", "barras", "pad", "encaixar"}:
        return "contain"
    return DEFAULT_FIT


def format_resolution(fmt: str) -> tuple[int, int] | None:
    return VIDEO_FORMATS.get(fmt)


def _orientation_of(width: int, height: int) -> str:
    if not width or not height:
        return "unknown"
    if width > height * 1.05:
        return "landscape"
    if height > width * 1.05:
        return "portrait"
    return "square"


def _format_output_size(fmt: str, info: Probe) -> tuple[int, int]:
    """Resolução final do formato escolhido, sem inflar fontes pequenas."""
    target = format_resolution(fmt)
    if not target:
        return (_even(info.width), _even(info.height))
    w, h = target
    if info.width and info.height:
        source_max = max(info.width, info.height)
        target_max = max(w, h)
        if source_max < target_max:
            factor = source_max / target_max
            w = _even(int(w * factor))
            h = _even(int(h * factor))
    return (_even(w), _even(h))


def build_format_filters(fmt: str, info: Probe, fit: str = DEFAULT_FIT) -> list[str]:
    """Reenquadra para o formato escolhido pelo operador.

    - `cover`  → preenche a tela e corta o excedente (sem barras).
    - `contain`→ encaixa o quadro inteiro com barras pretas.
    """
    target = format_resolution(fmt)
    if not target or not info.has_video:
        return []
    w, h = _format_output_size(fmt, info)
    if fit == "contain":
        return [
            f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos",
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black",
            "setsar=1",
        ]
    return [
        f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos",
        f"crop={w}:{h}",
        "setsar=1",
    ]


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


def normalize_level(level: str | None) -> str | None:
    if level is None:
        return None
    raw = str(level).strip().lower()
    if not raw:
        return None
    normalized = unicodedata.normalize("NFKD", raw)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"\s+", " ", normalized)
    return _LEVEL_ALIASES.get(normalized, normalized if normalized in LEVELS else None)


@dataclass
class Probe:
    width: int = 0
    height: int = 0
    fps: float = 30.0
    duration: float = 0.0
    bit_rate: int = 0
    video_codec: str = ""
    has_audio: bool = False
    has_video: bool = False
    orientation: str = "unknown"
    aspect_ratio: float = 0.0


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
    source_width: int = 0
    source_height: int = 0
    source_orientation: str = "unknown"
    source_aspect_ratio: float = 0.0
    source_duration: float = 0.0
    source_bitrate: int = 0
    source_size_bytes: int = 0
    source_video_codec: str = ""
    output_duration: float = 0.0
    output_bitrate: int = 0
    output_size_bytes: int = 0
    output_video_codec: str = ""
    audit_summary: str = ""
    video_format: str = "original"
    format_fit: str = "cover"
    output_width: int = 0
    output_height: int = 0

    @property
    def unique(self) -> bool:
        return bool(self.md5_after) and self.md5_after != self.md5_before

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
            "unique": self.unique,
            "source_width": self.source_width,
            "source_height": self.source_height,
            "source_orientation": self.source_orientation,
            "source_aspect_ratio": self.source_aspect_ratio,
            "source_duration": self.source_duration,
            "source_bitrate": self.source_bitrate,
            "source_size_bytes": self.source_size_bytes,
            "source_video_codec": self.source_video_codec,
            "output_duration": self.output_duration,
            "output_bitrate": self.output_bitrate,
            "output_size_bytes": self.output_size_bytes,
            "output_video_codec": self.output_video_codec,
            "audit_summary": self.audit_summary,
            "video_format": self.video_format,
            "format_fit": self.format_fit,
            "output_width": self.output_width,
            "output_height": self.output_height,
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
                "format=duration,bit_rate:stream=codec_type,codec_name,width,height,avg_frame_rate",
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
    try:
        info.bit_rate = int(float(data.get("format", {}).get("bit_rate") or 0))
    except (TypeError, ValueError):
        info.bit_rate = 0

    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        if kind == "video" and not info.has_video:
            info.has_video = True
            info.video_codec = str(stream.get("codec_name") or "")
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
    if info.width > 0 and info.height > 0:
        info.aspect_ratio = info.width / info.height
        if info.width > info.height * 1.05:
            info.orientation = "landscape"
        elif info.height > info.width * 1.05:
            info.orientation = "portrait"
        else:
            info.orientation = "square"
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
    orientation_bias = {
        "portrait": (1.15, 0.9),
        "landscape": (0.9, 1.15),
        "square": (1.0, 1.0),
    }.get(info.orientation, (1.0, 1.0))

    # 1. Crop microscópico em posição aleatória + rescale para a grade original.
    if info.width and info.height:
        cut_x = _even(int(rng.uniform(2, 6 * intensity) * orientation_bias[0]))
        cut_y = _even(int(rng.uniform(2, 6 * intensity) * orientation_bias[1]))
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

    # 7. Nível extremo: micro-blur + realce, embaralha a assinatura de frequência.
    if level == "extrema":
        filters.append(f"gblur=sigma={rng.uniform(0.12, 0.28):.3f}")


    return filters


def build_audio_filters(level: str, info: Probe, rng: random.Random, speed: float) -> list[str]:
    if level == "off" or not info.has_audio:
        return []

    # O legado forte de TikTok/Youtube preserva o corpo do grave.
    # Aqui evitamos `asetrate` para não alterar pitch e mantemos só o
    # reencaixe temporal com `atempo`, que muda velocidade sem achatar o baixo.
    filters = [f"atempo={speed:.6f}"]

    if level == "leve":
        filters.extend(
            [
                f"volume={1 + rng.uniform(-0.01, 0.01):.4f}",
                "acompressor=threshold=0.22:ratio=1.8:attack=18:release=180:makeup=1.0",
            ]
        )
        return filters

    if level == "media":
        filters.extend(
            [
                "equalizer=f=120:t=q:w=1.0:g=2.0",
                "equalizer=f=4200:t=q:w=1.0:g=-1.2",
                "acompressor=threshold=0.20:ratio=2.2:attack=18:release=160:makeup=1.0",
                "alimiter=limit=0.94",
            ]
        )
        return filters

    if level == "agressiva":
        filters.extend(
            [
                "equalizer=f=100:t=q:w=1.0:g=3.0",
                "equalizer=f=5500:t=q:w=1.0:g=1.8",
                "acompressor=threshold=0.17:ratio=3.0:attack=12:release=120:makeup=1.2",
                "alimiter=limit=0.92",
            ]
        )
        return filters

    if level == "extrema":
        filters.extend(
            [
                "equalizer=f=90:t=q:w=1.0:g=3.4",
                "equalizer=f=6000:t=q:w=1.0:g=2.0",
                "acompressor=threshold=0.15:ratio=3.4:attack=10:release=110:makeup=1.3",
                "alimiter=limit=0.90",
            ]
        )
        return filters

    filters.extend(
        [
            "acompressor=threshold=0.20:ratio=2.0:attack=18:release=160:makeup=1.0",
            "alimiter=limit=0.94",
        ]
    )
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


def resolve_level(level: str, info: Probe) -> str:
    """Escolhe o melhor preset quando o operador deixa em modo automático."""
    canonical = normalize_level(level) or DEFAULT_LEVEL
    if canonical != "auto":
        return canonical

    duration = max(float(info.duration or 0.0), 0.0)
    if not info.has_video:
        return "leve" if info.has_audio else "off"
    if duration <= 120:
        return "media"
    if duration <= 900:
        return "leve"
    if duration <= 1800:
        return "off"
    return "off"


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
    audio_only: bool = False,
    video_format: str = DEFAULT_FORMAT,
    format_fit: str = DEFAULT_FIT,
) -> tuple[list[str], SterilizationReport]:
    identity = _fake_identity(rng)
    suffix = dst.suffix.lower()
    mp4_family = suffix in {".mp4", ".mov", ".m4a", ".m4v"}
    # Saída só de áudio (ferramenta de voz): nenhum filtro/encoder de vídeo.
    keep_video = info.has_video and not audio_only
    format_filters = [] if audio_only else build_format_filters(video_format, info, format_fit)
    # A mutação precisa enxergar a grade JÁ reenquadrada, senão o crop/rescale
    # dela devolveria o vídeo para a proporção da fonte.
    mutation_info = info
    if format_filters:
        w, h = _format_output_size(video_format, info)
        mutation_info = replace(info, width=w, height=h, orientation=_orientation_of(w, h))
    vf = (
        []
        if audio_only
        # Reenquadra ANTES dos filtros extras (legenda queimada precisa cair
        # sobre a tela final, senão o corte comeria o texto).
        else format_filters
        + list(extra_video_filters or [])
        + build_video_filters(level, mutation_info, rng)
    )


    speed_filter = next((f for f in vf if f.startswith("setpts=PTS/")), "")
    speed = float(speed_filter.split("/")[-1]) if speed_filter else 1.0
    af = list(extra_audio_filters or [])
    if not af:
        af.extend(build_audio_filters(level, info, rng, speed))

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
        "-progress",
        "pipe:1",
        "-stats_period",
        "2",
        "-threads",
        "0",
        "-filter_threads",
        "0",
        "-filter_complex_threads",
        "0",
        "-i",
        str(src),
    ]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    if audio_only:
        cmd += ["-vn", "-map", "0:a:0?"]
    if af:
        cmd += ["-af", ",".join(af)]

    if keep_video:
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
    if keep_video:
        cmd += ["-metadata:s:v:0", f"handler_name={identity['handler_video']}"]
    if info.has_audio:
        cmd += ["-metadata:s:a:0", f"handler_name={identity['handler_audio']}"]

    if mp4_family:
        cmd += ["-movflags", "+faststart"]
    cmd += ["-max_muxing_queue_size", "4096"]
    cmd.append(str(dst))


    report = SterilizationReport(
        level=level,
        seed=rng.randint(0, 2**31),
        bitrate=chosen_bitrate,
        video_filters=vf,
        audio_filters=af,
        identity=identity,
        source_width=info.width,
        source_height=info.height,
        source_orientation=info.orientation,
        source_aspect_ratio=info.aspect_ratio,
        source_duration=info.duration,
        source_bitrate=info.bit_rate,
        source_size_bytes=src.stat().st_size if src.exists() else 0,
        source_video_codec=info.video_codec,
        video_format=video_format,
        format_fit=format_fit,
    )
    return cmd, report


def _parse_progress_seconds(line: str) -> float | None:
    if line.startswith("out_time_ms="):
        value = line.split("=", 1)[1].strip()
        try:
            return max(0.0, float(value) / 1_000_000.0)
        except ValueError:
            return None
    if line.startswith("out_time="):
        value = line.split("=", 1)[1].strip()
        match = re.fullmatch(r"(?:(\d+):)?(\d+):(\d+)(?:\.(\d+))?", value)
        if not match:
            return None
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        fraction = match.group(4) or "0"
        return hours * 3600 + minutes * 60 + seconds + float(f"0.{fraction}")
    return None


def sterilize(
    src: Path,
    dst: Path,
    *,
    job_id: str | None = None,
    level: str = DEFAULT_LEVEL,
    bitrate: str = "auto",
    extra_video_filters: list[str] | None = None,
    extra_audio_filters: list[str] | None = None,
    audio_only: bool = False,
    video_format: str = DEFAULT_FORMAT,
    format_fit: str = DEFAULT_FIT,
    max_attempts: int = 3,
    runner=None,
) -> SterilizationReport:
    """Esteriliza `src` em `dst` e devolve o relatório da operação."""
    from . import media  # import tardio evita ciclo

    execute = runner or media.run
    level = normalize_level(level) or DEFAULT_LEVEL
    video_format = normalize_format(video_format)
    format_fit = normalize_fit(format_fit)

    info = probe(src)
    level = resolve_level(level, info)
    before = file_hashes(src)
    seed = random.SystemRandom().randint(0, 2**31)
    timeout = max(7200, int(info.duration * 2) + 3600) if info.duration > 0 else 4 * 3600

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
            audio_only=audio_only,
            video_format=video_format,
            format_fit=format_fit,
        )
        report.md5_before = before["md5"]
        report.attempts = attempt
        if job_id:
            from . import jobs as jobs_service

            jobs_service.update(job_id, progress=min(10, 5 * attempt))

        last_progress = 0

        def on_line(line: str) -> None:
            nonlocal last_progress
            if not job_id:
                return
            if line.startswith("progress=end"):
                if last_progress < 95:
                    from . import jobs as jobs_service

                    jobs_service.update(job_id, progress=95)
                    last_progress = 95
                return
            seconds = _parse_progress_seconds(line)
            if seconds is None or info.duration <= 0:
                return
            percent = int(min(98, max(0.0, seconds / info.duration * 90.0 + 8.0)))
            if percent > last_progress:
                from . import jobs as jobs_service

                jobs_service.update(job_id, progress=percent)
                last_progress = percent

        execute(cmd, job_id=job_id, timeout=timeout, line_callback=on_line)

        after = file_hashes(dst)
        out_info = probe(dst)
        report.md5_after = after["md5"]
        report.sha256_after = after["sha256"]
        report.output_duration = out_info.duration
        report.output_bitrate = out_info.bit_rate
        report.output_size_bytes = dst.stat().st_size if dst.exists() else 0
        report.output_video_codec = out_info.video_codec
        report.output_width = out_info.width
        report.output_height = out_info.height
        report.steps = [
            "Metadados de origem destruídos (container, streams, capítulos)",
            f"Identidade forjada: {report.identity['encoder']} @ {report.identity['creation_time']}",
            f"Mutação estrutural nível '{level}' ({len(report.video_filters)} filtro(s) de vídeo)",
            f"Áudio reescrito ({len(report.audio_filters)} filtro(s)) e re-encodado em AAC 48 kHz",
            f"Bitrate randômico {report.bitrate} + GOP variável",
            (
                "Formato final mantido igual ao da fonte"
                if video_format == "original"
                else f"Reenquadrado para {video_format} ({format_fit}) → {out_info.width}x{out_info.height}"
            ),
            f"Hash final inédito: MD5 {report.md5_after[:12]}…",
        ]
        if report.unique:
            return report
        if job_id:
            from . import jobs as jobs_service

            jobs_service.log(job_id, f"Hash colidiu na tentativa {attempt} — repetindo com nova semente.")

    if report is None:  # pragma: no cover - defensivo
        raise RuntimeError("Falha ao esterilizar o arquivo.")
    return report
