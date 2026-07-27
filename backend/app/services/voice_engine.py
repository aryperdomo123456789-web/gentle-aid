"""Motor de voz profissional — TTS e Speech-to-Speech (ElevenLabs) com chunking.

Fluxos suportados:

* **V2V / Speech-to-Speech**: troca o timbre do narrador preservando a narrativa,
  a entonação e o timing. Áudios longos (até horas) são fatiados em silêncios,
  convertidos em série e recolados sem emenda.
* **TTS**: transforma texto em narração com vozes realistas.
* **Fallback local**: quando não existe chave ElevenLabs no cofre, o sistema cai
  para a cadeia FFmpeg de mudança de timbre (sem custo, qualidade inferior).

Todas as chamadas usam a chave do cofre (`api_keys.get_key("elevenlabs")`), que
espelha `ELEVENLABS_API_KEY` no `.env`.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from ..config import config
from . import api_keys, jobs, media

API_BASE = "https://api.elevenlabs.io/v1"
STS_MODEL = "eleven_multilingual_sts_v2"
TTS_MODEL = "eleven_multilingual_v2"

# Fatia alvo de áudio enviada por requisição (segundos). Mantém latência baixa,
# custo previsível e evita limites de payload da API.
CHUNK_TARGET = 240.0
CHUNK_MAX = 300.0
TEXT_CHUNK = 2200

# Catálogo curado (usado como fallback quando a API não responde a lista).
FALLBACK_VOICES = [
    {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "labels": "masculino · narração"},
    {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel", "labels": "masculino · documentário"},
    {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian", "labels": "masculino · profundo"},
    {"id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam", "labels": "masculino · jovem"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah", "labels": "feminino · suave"},
    {"id": "Xb7hH8MSUJpSbSDYk0k2", "name": "Alice", "labels": "feminino · clara"},
    {"id": "cgSgspJ2msm6clMCkdW9", "name": "Jessica", "labels": "feminino · energética"},
    {"id": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda", "labels": "feminino · narração"},
]


class VoiceEngineError(RuntimeError):
    """Erro de negócio do motor de voz (mensagem já pronta para o operador)."""


@dataclass
class Settings:
    stability: float = 0.5
    similarity_boost: float = 0.85
    style: float = 0.0
    speaker_boost: bool = True

    def payload(self) -> dict[str, object]:
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "use_speaker_boost": self.speaker_boost,
        }


def api_key() -> str | None:
    return api_keys.get_key("elevenlabs")


def available() -> bool:
    return bool(api_key())


def _request(path: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None,
             timeout: int = 600) -> bytes:
    key = api_key()
    if not key:
        raise VoiceEngineError(
            "Nenhuma chave ElevenLabs configurada. Cadastre em /apis (provedor ElevenLabs) para liberar as vozes realistas."
        )
    req = urllib.request.Request(f"{API_BASE}{path}", data=data, method=method)
    req.add_header("xi-api-key", key)
    req.add_header("accept", "*/*")
    for name, value in (headers or {}).items():
        req.add_header(name, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - host fixo
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")[:400]
        raise VoiceEngineError(_explain(exc.code, body)) from exc
    except urllib.error.URLError as exc:
        raise VoiceEngineError(f"Falha de rede ao falar com a ElevenLabs: {exc.reason}") from exc


def _explain(status: int, body: str) -> str:
    if status == 401:
        return "ElevenLabs recusou a chave (401). Gere uma nova em elevenlabs.io → Profile → API Key e atualize em /apis."
    if status == 402 or "quota" in body.lower():
        return "Créditos de voz esgotados na ElevenLabs (402). Recarregue o plano ou reduza o tamanho do áudio."
    if status == 422:
        return f"Requisição rejeitada pela ElevenLabs (422): {body}"
    if status == 429:
        return "Limite de requisições da ElevenLabs atingido (429). Aguarde alguns segundos e repita."
    return f"ElevenLabs respondeu {status}: {body}"


# --------------------------------------------------------------------------- #
# Catálogo de vozes
# --------------------------------------------------------------------------- #
def list_voices() -> list[dict[str, str]]:
    if not available():
        return list(FALLBACK_VOICES)
    try:
        raw = _request("/voices", timeout=30)
        data = json.loads(raw.decode("utf-8", "ignore"))
    except (VoiceEngineError, json.JSONDecodeError):
        return list(FALLBACK_VOICES)

    voices: list[dict[str, str]] = []
    for item in data.get("voices", []) or []:
        labels = item.get("labels") or {}
        descriptor = " · ".join(
            str(labels[k]) for k in ("gender", "accent", "use_case", "description") if labels.get(k)
        )
        voices.append(
            {
                "id": item.get("voice_id", ""),
                "name": item.get("name", "sem nome"),
                "labels": descriptor,
                "preview_url": item.get("preview_url") or "",
            }
        )
    voices = [v for v in voices if v["id"]]
    return voices or list(FALLBACK_VOICES)


# --------------------------------------------------------------------------- #
# Fatiamento de áudio longo
# --------------------------------------------------------------------------- #
def _silence_points(src: Path, job_id: str | None) -> list[float]:
    """Devolve instantes (s) de silêncio detectados — bons pontos de corte."""
    try:
        out = media.run(
            [
                config.ffmpeg_bin, "-hide_banner", "-nostats", "-i", str(src),
                "-af", "silencedetect=noise=-32dB:d=0.45", "-f", "null", "-",
            ],
            job_id=None,
            timeout=3600,
        )
    except RuntimeError:
        return []
    points: list[float] = []
    for match in re.finditer(r"silence_(?:start|end):\s*([0-9.]+)", out):
        try:
            points.append(float(match.group(1)))
        except ValueError:
            continue
    if job_id and points:
        jobs.log(job_id, f"Detectados {len(points)} pontos de silêncio para corte limpo.")
    return sorted(points)


def plan_cuts(duration: float, silences: list[float]) -> list[tuple[float, float]]:
    """Monta as fatias (início, fim) respeitando silêncios quando possível."""
    if duration <= CHUNK_MAX:
        return [(0.0, duration)]
    cuts: list[tuple[float, float]] = []
    start = 0.0
    while start < duration - 0.5:
        target = start + CHUNK_TARGET
        if target >= duration:
            cuts.append((start, duration))
            break
        candidates = [s for s in silences if start + 45 < s <= start + CHUNK_MAX]
        end = min(candidates, key=lambda s: abs(s - target)) if candidates else min(target, duration)
        if end - start < 5:
            end = min(start + CHUNK_TARGET, duration)
        cuts.append((start, end))
        start = end
    return cuts


def _slice_audio(src: Path, start: float, end: float, dst: Path, job_id: str) -> None:
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
            "-vn", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=None,
    )
    if not dst.exists() or dst.stat().st_size == 0:
        raise VoiceEngineError(f"Falha ao fatiar o áudio em {start:.1f}s.")


def _concat(parts: list[Path], dst: Path, job_id: str) -> None:
    listing = dst.with_suffix(".concat.txt")
    listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c:a", "pcm_s16le", "-ar", "44100", str(dst),
        ],
        job_id=job_id,
    )
    listing.unlink(missing_ok=True)


def _fit_duration(src: Path, target: float, dst: Path) -> None:
    """Ajusta a fatia convertida para bater exatamente com a duração original."""
    current = media.probe_duration(src)
    if current <= 0 or target <= 0:
        src.replace(dst)
        return
    ratio = current / target
    if abs(ratio - 1) < 0.005:
        src.replace(dst)
        return
    ratio = max(0.5, min(2.0, ratio))
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src), "-filter:a", f"atempo={ratio:.6f}",
            "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=None,
    )
    src.unlink(missing_ok=True)


def _multipart(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = "----viralvoice7f3a9d"
    buf = bytearray()
    for name, value in fields.items():
        buf += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    buf += (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
        f"filename=\"{file_path.name}\"\r\nContent-Type: audio/wav\r\n\r\n"
    ).encode()
    buf += file_path.read_bytes()
    buf += f"\r\n--{boundary}--\r\n".encode()
    return bytes(buf), f"multipart/form-data; boundary={boundary}"


# --------------------------------------------------------------------------- #
# Speech-to-Speech (troca o narrador, mantém a narrativa)
# --------------------------------------------------------------------------- #
def speech_to_speech(
    src: Path,
    dst_wav: Path,
    *,
    voice_id: str,
    job_id: str,
    settings: Settings | None = None,
    keep_timing: bool = True,
    remove_noise: bool = True,
) -> Path:
    settings = settings or Settings()
    duration = media.probe_duration(src)
    if duration <= 0:
        raise VoiceEngineError("Não foi possível ler a duração do áudio de origem.")

    workdir = dst_wav.parent / f"{job_id}_sts"
    workdir.mkdir(parents=True, exist_ok=True)

    silences = _silence_points(src, job_id) if duration > CHUNK_MAX else []
    cuts = plan_cuts(duration, silences)
    jobs.log(
        job_id,
        f"Speech-to-Speech ElevenLabs · {duration/60:.1f} min em {len(cuts)} fatia(s) · voz {voice_id}",
    )

    parts: list[Path] = []
    for index, (start, end) in enumerate(cuts, start=1):
        chunk_in = workdir / f"in_{index:04d}.wav"
        raw_out = workdir / f"raw_{index:04d}.wav"
        fitted = workdir / f"out_{index:04d}.wav"
        _slice_audio(src, start, end, chunk_in, job_id)

        body, content_type = _multipart(
            {
                "model_id": STS_MODEL,
                "remove_background_noise": "true" if remove_noise else "false",
                "voice_settings": json.dumps(settings.payload()),
            },
            "audio",
            chunk_in,
        )
        audio = _request(
            f"/speech-to-speech/{voice_id}?output_format=pcm_44100",
            method="POST",
            data=body,
            headers={"Content-Type": content_type},
        )
        _write_pcm(audio, raw_out)
        if keep_timing:
            _fit_duration(raw_out, end - start, fitted)
        else:
            raw_out.replace(fitted)
        parts.append(fitted)
        chunk_in.unlink(missing_ok=True)

        progress = 20 + int(60 * index / len(cuts))
        jobs.update(job_id, progress=min(85, progress))
        jobs.log(job_id, f"Fatia {index}/{len(cuts)} convertida ({start:.0f}s → {end:.0f}s).")

    if len(parts) == 1:
        parts[0].replace(dst_wav)
    else:
        _concat(parts, dst_wav, job_id)
    for leftover in workdir.glob("*"):
        leftover.unlink(missing_ok=True)
    workdir.rmdir()
    return dst_wav


def _write_pcm(pcm: bytes, dst: Path) -> None:
    """Converte PCM cru 44.1 kHz mono em WAV navegável."""
    raw = dst.with_suffix(".pcm")
    raw.write_bytes(pcm)
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "s16le", "-ar", "44100", "-ac", "1", "-i", str(raw),
            "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=None,
    )
    raw.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Texto → narração
# --------------------------------------------------------------------------- #
def split_text(text: str, limit: int = TEXT_CHUNK) -> list[str]:
    text = re.sub(r"\s+\n", "\n", text.strip())
    if len(text) <= limit:
        return [text] if text else []
    sentences = re.findall(r"[^.!?\n]+[.!?\n]*", text) or [text]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > limit:
            if current.strip():
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(sentence), limit):
                chunks.append(sentence[i : i + limit].strip())
            continue
        if len(current) + len(sentence) > limit:
            chunks.append(current.strip())
            current = ""
        current += sentence
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]


def text_to_speech(
    text: str,
    dst_wav: Path,
    *,
    voice_id: str,
    job_id: str,
    settings: Settings | None = None,
    speed: float = 1.0,
) -> Path:
    settings = settings or Settings(stability=0.45, similarity_boost=0.8, style=0.15)
    chunks = split_text(text)
    if not chunks:
        raise VoiceEngineError("Nenhum texto para narrar.")

    workdir = dst_wav.parent / f"{job_id}_tts"
    workdir.mkdir(parents=True, exist_ok=True)
    jobs.log(job_id, f"Narração ElevenLabs · {len(text)} caracteres em {len(chunks)} bloco(s) · voz {voice_id}")

    parts: list[Path] = []
    for index, chunk in enumerate(chunks, start=1):
        part = workdir / f"tts_{index:04d}.wav"
        voice_settings = settings.payload()
        if abs(speed - 1.0) > 0.001:
            voice_settings["speed"] = max(0.7, min(1.2, speed))
        payload = json.dumps(
            {
                "text": chunk,
                "model_id": TTS_MODEL,
                "voice_settings": voice_settings,
                **({"previous_text": chunks[index - 2]} if index > 1 else {}),
                **({"next_text": chunks[index]} if index < len(chunks) else {}),
            }
        ).encode("utf-8")
        audio = _request(
            f"/text-to-speech/{voice_id}?output_format=pcm_44100",
            method="POST",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        _write_pcm(audio, part)
        parts.append(part)
        jobs.update(job_id, progress=min(85, 20 + int(60 * index / len(chunks))))
        jobs.log(job_id, f"Bloco {index}/{len(chunks)} narrado.")

    if len(parts) == 1:
        parts[0].replace(dst_wav)
    else:
        _concat(parts, dst_wav, job_id)
    for leftover in workdir.glob("*"):
        leftover.unlink(missing_ok=True)
    workdir.rmdir()
    return dst_wav


# --------------------------------------------------------------------------- #
# Remux: devolve a nova narração para dentro do vídeo original
# --------------------------------------------------------------------------- #
def swap_video_audio(video: Path, audio: Path, dst: Path, job_id: str) -> Path:
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(dst),
        ],
        job_id=job_id,
    )
    return dst
