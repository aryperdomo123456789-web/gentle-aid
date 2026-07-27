"""Motor base gratuito — Edge TTS (vozes neurais da Microsoft, sem chave).

Serve como matéria-prima do Voice Forge: o Edge TTS gera a fala, o
`voice_forge` aplica a assinatura acústica própria por cima. Assim a voz final
não é a voz padrão de ninguém — é a persona do projeto.

Dependência: pacote `edge-tts` (puro Python, sem chave de API). Se não estiver
instalado, o motor se declara indisponível e a UI cai para ElevenLabs/local.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from ..config import config
from . import jobs, media

# Blocos de texto por requisição — evita timeouts em roteiros longos.
TEXT_CHUNK = 1800

FALLBACK_VOICES = [
    {"id": "pt-BR-AntonioNeural", "name": "Antonio (pt-BR)", "labels": "masculino · neutro"},
    {"id": "pt-BR-FranciscaNeural", "name": "Francisca (pt-BR)", "labels": "feminino · neutro"},
    {"id": "pt-BR-ThalitaNeural", "name": "Thalita (pt-BR)", "labels": "feminino · jovem"},
    {"id": "pt-PT-DuarteNeural", "name": "Duarte (pt-PT)", "labels": "masculino · europeu"},
    {"id": "en-US-GuyNeural", "name": "Guy (en-US)", "labels": "masculino · narração"},
    {"id": "en-US-AriaNeural", "name": "Aria (en-US)", "labels": "feminino · clara"},
    {"id": "es-MX-JorgeNeural", "name": "Jorge (es-MX)", "labels": "masculino · latino"},
]


class EdgeTTSError(RuntimeError):
    """Erro do motor gratuito, com mensagem pronta para o operador."""


def _module():
    try:
        import edge_tts  # type: ignore
    except ImportError:  # pragma: no cover - depende do ambiente
        return None
    return edge_tts


def available() -> bool:
    return _module() is not None


def list_voices(locale_prefixes: tuple[str, ...] = ("pt", "en", "es")) -> list[dict[str, str]]:
    module = _module()
    if module is None:
        return list(FALLBACK_VOICES)
    try:
        raw = asyncio.run(module.list_voices())
    except Exception:  # noqa: BLE001 - rede/API instável não pode derrubar o catálogo
        return list(FALLBACK_VOICES)

    voices: list[dict[str, str]] = []
    for item in raw or []:
        short = item.get("ShortName") or ""
        if not short or not short.lower().startswith(locale_prefixes):
            continue
        tags = item.get("VoiceTag") or {}
        personalities = ", ".join(tags.get("VoicePersonalities") or [])
        voices.append(
            {
                "id": short,
                "name": f"{item.get('FriendlyName', short).replace('Microsoft ', '')}",
                "labels": " · ".join(x for x in (item.get("Gender", ""), personalities) if x),
            }
        )
    voices.sort(key=lambda v: (not v["id"].startswith("pt-BR"), v["id"]))
    return voices or list(FALLBACK_VOICES)


def split_text(text: str, limit: int = TEXT_CHUNK) -> list[str]:
    text = text.strip()
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


async def _synth_one(text: str, voice: str, rate: str, dst_mp3: Path) -> None:
    module = _module()
    assert module is not None
    communicate = module.Communicate(text, voice, rate=rate)
    await communicate.save(str(dst_mp3))


def synthesize(
    text: str,
    dst_wav: Path,
    *,
    voice: str,
    job_id: str,
    rate_percent: int = 0,
) -> Path:
    """Gera narração bruta (sem persona aplicada) em WAV 48 kHz mono."""
    module = _module()
    if module is None:
        raise EdgeTTSError(
            "Motor gratuito indisponível: instale a dependência `edge-tts` no servidor "
            "(`.venv/bin/pip install edge-tts`) e reinicie o serviço viral-api."
        )
    chunks = split_text(text)
    if not chunks:
        raise EdgeTTSError("Nenhum texto para narrar.")

    workdir = dst_wav.parent / f"{job_id}_edge"
    workdir.mkdir(parents=True, exist_ok=True)
    rate = f"{rate_percent:+d}%"
    jobs.log(job_id, f"Motor gratuito Edge TTS · voz base {voice} · {len(chunks)} bloco(s) · rate {rate}")

    parts: list[Path] = []
    try:
        for index, chunk in enumerate(chunks, start=1):
            mp3 = workdir / f"edge_{index:04d}.mp3"
            wav = workdir / f"edge_{index:04d}.wav"
            try:
                asyncio.run(_synth_one(chunk, voice, rate, mp3))
            except Exception as exc:  # noqa: BLE001 - erro de rede/voz inválida
                raise EdgeTTSError(f"Falha no motor gratuito ao narrar o bloco {index}: {exc}") from exc
            if not mp3.exists() or mp3.stat().st_size == 0:
                raise EdgeTTSError(f"O motor gratuito devolveu áudio vazio no bloco {index}.")
            media.run(
                [
                    config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(mp3), "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(wav),
                ],
                job_id=None,
            )
            mp3.unlink(missing_ok=True)
            parts.append(wav)
            jobs.update(job_id, progress=min(70, 15 + int(55 * index / len(chunks))))

        if len(parts) == 1:
            parts[0].replace(dst_wav)
        else:
            listing = workdir / "concat.txt"
            listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
            media.run(
                [
                    config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(dst_wav),
                ],
                job_id=job_id,
            )
    finally:
        for leftover in workdir.glob("*"):
            leftover.unlink(missing_ok=True)
        workdir.rmdir()
    return dst_wav
