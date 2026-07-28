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
import time
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

# Locales oferecidos no catálogo e usados pela dublagem multi-idioma.
LOCALE_PREFIXES = ("pt", "en", "es", "fr", "it", "de", "ja", "ko", "zh", "ru", "ar", "hi", "tr", "id")

# Matéria-prima por idioma: (voz masculina, voz feminina).
# A dublagem precisa falar o idioma alvo com um locutor nativo — uma voz pt-BR
# lendo inglês sai com sotaque quebrado e derruba a retenção.
LANG_VOICES: dict[str, tuple[str, str]] = {
    "pt": ("pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"),
    "en": ("en-US-GuyNeural", "en-US-AriaNeural"),
    "es": ("es-MX-JorgeNeural", "es-ES-ElviraNeural"),
    "fr": ("fr-FR-HenriNeural", "fr-FR-DeniseNeural"),
    "it": ("it-IT-DiegoNeural", "it-IT-ElsaNeural"),
    "de": ("de-DE-ConradNeural", "de-DE-KatjaNeural"),
    "ja": ("ja-JP-KeitaNeural", "ja-JP-NanamiNeural"),
    "ko": ("ko-KR-InJoonNeural", "ko-KR-SunHiNeural"),
    "zh": ("zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural"),
    "ru": ("ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"),
    "ar": ("ar-EG-ShakirNeural", "ar-EG-SalmaNeural"),
    "hi": ("hi-IN-MadhurNeural", "hi-IN-SwaraNeural"),
    "tr": ("tr-TR-AhmetNeural", "tr-TR-EmelNeural"),
    "id": ("id-ID-ArdiNeural", "id-ID-GadisNeural"),
}

# Vozes femininas conhecidas do catálogo pt-BR/pt-PT usadas como base das personas.
_FEMALE_HINTS = (
    "francisca", "thalita", "brenda", "elza", "giovanna", "leila", "leticia", "manuela",
    "yara", "raquel", "fernanda", "aria", "jenny", "michelle", "ana", "elvira", "dalia",
    "denise", "elsa", "katja", "nanami", "sunhi", "xiaoxiao", "svetlana", "salma", "swara",
    "emel", "gadis",
)


def language_of(voice_id: str) -> str:
    """`pt-BR-AntonioNeural` → `pt`."""
    return (voice_id or "").split("-", 1)[0].lower()


def is_female(voice_id: str) -> bool:
    lowered = (voice_id or "").lower()
    return any(hint in lowered for hint in _FEMALE_HINTS)


def voice_for_language(language: str, *, prefer: str = "") -> str:
    """Voz nativa do idioma alvo, mantendo o gênero da voz preferida.

    `prefer` é a voz base da persona do usuário. Se ela já fala o idioma alvo,
    é devolvida intacta (a identidade da voz própria é preservada).
    """
    lang = (language or "").split("-", 1)[0].lower()
    if not lang or lang == "auto":
        return prefer or FALLBACK_VOICES[0]["id"]
    if prefer and language_of(prefer) == lang:
        return prefer
    pair = LANG_VOICES.get(lang)
    if not pair:
        return prefer or FALLBACK_VOICES[0]["id"]
    return pair[1] if (prefer and is_female(prefer)) else pair[0]



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


def list_voices(locale_prefixes: tuple[str, ...] = LOCALE_PREFIXES) -> list[dict[str, str]]:
    module = _module()
    if module is None:
        return list(FALLBACK_VOICES)
    try:
        raw = _run_async(module.list_voices())
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


def _run_async(coro):
    """Executa a corrotina em um loop próprio, sem depender do `asyncio.run`.

    `asyncio.run` cria executores auxiliares que, durante o shutdown do
    interpretador (reciclagem/restart do worker do Gunicorn), estouram
    `cannot schedule new futures after interpreter shutdown` e derrubam jobs
    longos de voz. Aqui o loop é criado, usado e fechado explicitamente na
    própria thread do job.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        finally:
            asyncio.set_event_loop(None)


async def _synth_one(text: str, voice: str, rate: str, dst_mp3: Path) -> None:
    module = _module()
    assert module is not None
    communicate = module.Communicate(text, voice, rate=rate)
    await communicate.save(str(dst_mp3))


# Roteiros longos derrubam a conexão do Edge TTS de vez em quando; o bloco é
# refeito em vez de matar o job inteiro.
SYNTH_ATTEMPTS = 3



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
            jobs.check_cancelled(job_id)
            mp3 = workdir / f"edge_{index:04d}.mp3"
            wav = workdir / f"edge_{index:04d}.wav"
            last_error: Exception | None = None
            for attempt in range(1, SYNTH_ATTEMPTS + 1):
                try:
                    mp3.unlink(missing_ok=True)
                    _run_async(_synth_one(chunk, voice, rate, mp3))
                    if not mp3.exists() or mp3.stat().st_size == 0:
                        raise EdgeTTSError("áudio vazio devolvido pelo provedor")
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - erro de rede/voz inválida
                    last_error = exc
                    if attempt < SYNTH_ATTEMPTS:
                        jobs.log(
                            job_id,
                            f"Bloco {index}: tentativa {attempt} falhou ({exc}). Refazendo…",
                            level="warn",
                        )
                        time.sleep(1.5 * attempt)
            if last_error is not None:
                raise EdgeTTSError(
                    f"Falha no motor gratuito ao narrar o bloco {index} "
                    f"após {SYNTH_ATTEMPTS} tentativas: {last_error}"
                ) from last_error

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
