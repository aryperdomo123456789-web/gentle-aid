"""Dublagem com IA — ouve a narração original e refaz com a sua voz.

Fluxo completo (o mesmo para upload, link do YouTube ou link do TikTok):

1. **Ouvir**: Whisper transcreve a fala com timestamps (`transcribe.py`).
2. **Traduzir** (opcional): LLM converte o roteiro para o idioma alvo mantendo
   a narrativa, o tom e o número de trechos.
3. **Narrar**: cada trecho é sintetizado com a voz escolhida (Voice Forge sobre
   Edge TTS, ou ElevenLabs).
4. **Sincronizar**: cada trecho é ajustado por `atempo` para caber na janela de
   tempo original e colado numa linha do tempo com silêncios exatos — a dublagem
   fica em cima da boca/corte do vídeo original.
5. **Assinar**: a persona aplica a assinatura acústica e a trilha volta pro vídeo.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from ..config import config
from . import api_keys, edge_tts, jobs, media, voice_engine, voice_forge
from .transcribe import Segment

SAMPLE_RATE = 48000
# Limites de elasticidade: além disso a fala fica robótica, então preferimos
# deixar o trecho invadir levemente o silêncio seguinte.
MIN_TEMPO = 0.75
MAX_TEMPO = 1.6

LANGUAGES = {
    "auto": "mesmo idioma do vídeo",
    "pt": "português do Brasil",
    "en": "inglês",
    "es": "espanhol",
    "fr": "francês",
    "it": "italiano",
    "de": "alemão",
}


class DubbingError(RuntimeError):
    """Erro de negócio da dublagem."""


# --------------------------------------------------------------------------- #
# Tradução (mantém a narrativa)
# --------------------------------------------------------------------------- #
_LLM_ROUTES = {
    "deepseek": ("https://api.deepseek.com/chat/completions", "deepseek-chat"),
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat"),
    "mistral": ("https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
}


def _llm(prompt: str, timeout: int = 120) -> str | None:
    for provider in api_keys.rank_providers(list(_LLM_ROUTES)):
        url, model = _LLM_ROUTES[provider]
        key = api_keys.get_key(provider)
        if not key:
            continue
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {key}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8", "ignore"))
            return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError):
            continue
    return None


def translate(segments: list[Segment], target: str, job_id: str) -> list[Segment]:
    """Traduz preservando a quantidade e a ordem dos trechos."""
    if target in ("", "auto"):
        return segments
    label = LANGUAGES.get(target, target)
    out: list[Segment] = []
    batch = 40
    for start in range(0, len(segments), batch):
        window = segments[start : start + batch]
        payload = [{"i": i, "t": seg.text} for i, seg in enumerate(window)]
        prompt = (
            f"Traduza para {label} os trechos de narração abaixo, mantendo o sentido, o tom e "
            "um comprimento parecido (a dublagem precisa caber no mesmo tempo). "
            "Responda SOMENTE JSON: {\"itens\":[{\"i\":0,\"t\":\"tradução\"}]}.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        raw = _llm(prompt)
        translated = {}
        if raw:
            try:
                chunk = raw[raw.find("{") : raw.rfind("}") + 1]
                for item in json.loads(chunk).get("itens", []):
                    translated[int(item["i"])] = str(item["t"]).strip()
            except (ValueError, KeyError, TypeError):
                translated = {}
        if not translated:
            jobs.log(job_id, "Tradução indisponível — seguindo com o texto original.")
            return segments
        for index, seg in enumerate(window):
            out.append(Segment(seg.start, seg.end, translated.get(index, seg.text)))
    jobs.log(job_id, f"Roteiro traduzido para {label}.")
    return out


# --------------------------------------------------------------------------- #
# Síntese por trecho
# --------------------------------------------------------------------------- #
def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _synth(text: str, dst: Path, *, engine: str, voice: str, job_id: str) -> Path:
    if engine == "elevenlabs":
        voice_engine.text_to_speech(text, dst, voice_id=voice, job_id=job_id)
    else:
        edge_tts.synthesize(text, dst, voice=voice, job_id=job_id)
    return dst


def _fit(src: Path, dst: Path, target: float) -> float:
    """Ajusta o trecho à janela original. Devolve a duração final real."""
    current = media.probe_duration(src)
    if current <= 0:
        src.replace(dst)
        return 0.0
    ratio = current / target if target > 0 else 1.0
    ratio = max(MIN_TEMPO, min(MAX_TEMPO, ratio))
    if abs(ratio - 1) < 0.01:
        src.replace(dst)
        return current
    steps: list[float] = []
    remaining = ratio
    while remaining > 2.0:
        steps.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        steps.append(0.5)
        remaining /= 0.5
    steps.append(remaining)
    chain = ",".join(f"atempo={s:.6f}" for s in steps)
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src), "-filter:a", chain,
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=None,
    )
    src.unlink(missing_ok=True)
    return media.probe_duration(dst)


def _silence(seconds: float, dst: Path) -> Path:
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono",
            "-t", f"{max(0.01, seconds):.3f}", "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=None,
    )
    return dst


def _concat(parts: list[Path], dst: Path, job_id: str) -> Path:
    listing = dst.parent / f"{dst.stem}_concat.txt"
    listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=job_id,
    )
    listing.unlink(missing_ok=True)
    return dst


def build_track(
    segments: list[Segment],
    dst_wav: Path,
    *,
    engine: str,
    voice: str,
    job_id: str,
    total_duration: float,
) -> Path:
    """Monta a trilha dublada inteira, sincronizada com o vídeo original."""
    work = dst_wav.parent / f"{job_id}_dub"
    work.mkdir(parents=True, exist_ok=True)
    timeline: list[Path] = []
    cursor = 0.0
    try:
        for index, seg in enumerate(segments, start=1):
            text = _clean(seg.text)
            if not text:
                continue
            if seg.start > cursor + 0.05:
                gap = work / f"gap_{index:04d}.wav"
                timeline.append(_silence(seg.start - cursor, gap))
                cursor = seg.start

            raw = work / f"raw_{index:04d}.wav"
            fitted = work / f"seg_{index:04d}.wav"
            _synth(text, raw, engine=engine, voice=voice, job_id=job_id)
            spoken = _fit(raw, fitted, seg.duration)
            timeline.append(fitted)
            cursor += spoken or seg.duration
            jobs.update(job_id, progress=min(80, 45 + int(35 * index / max(1, len(segments)))))
            if index % 5 == 0 or index == len(segments):
                jobs.log(job_id, f"Dublagem {index}/{len(segments)} trechos narrados.")

        if not timeline:
            raise DubbingError("Nenhum trecho de fala pôde ser dublado.")

        if total_duration > cursor + 0.2:
            tail = work / "tail.wav"
            timeline.append(_silence(total_duration - cursor, tail))

        _concat(timeline, dst_wav, job_id)
    finally:
        for leftover in work.glob("*"):
            leftover.unlink(missing_ok=True)
        work.rmdir()
    return dst_wav


def apply_persona(src: Path, dst: Path, persona, job_id: str) -> Path:
    """Aplica a assinatura acústica da voz própria por cima da narração."""
    chain = voice_forge.filter_chain(persona, preserve_duration=True)
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src), "-filter:a", ",".join(chain),
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=job_id,
    )
    src.unlink(missing_ok=True)
    return dst


def mix_with_background(video: Path, dub: Path, dst: Path, *, keep_ambience: float, job_id: str) -> Path:
    """Mantém a trilha original em volume baixo (música/ambiência) sob a dublagem."""
    if keep_ambience <= 0:
        return voice_engine.swap_video_audio(video, dub, dst, job_id)
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video), "-i", str(dub),
            "-filter_complex",
            f"[0:a]volume={keep_ambience:.2f},highpass=f=180[bg];"
            "[1:a]volume=1.0[vo];[bg][vo]amix=inputs=2:duration=first:dropout_transition=0[a]",
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(dst),
        ],
        job_id=job_id,
    )
    return dst
