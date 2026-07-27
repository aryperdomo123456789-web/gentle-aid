"""Ferramenta 4 — Estúdio de Voz.

Três fluxos, um motor:

1. **Vídeo → nova voz**: extrai a narração, troca o narrador (Speech-to-Speech)
   preservando a narrativa e devolve o áudio novo dentro do vídeo original.
2. **Áudio → nova voz**: mesmo fluxo para arquivos de 10 segundos a várias horas
   (fatiamento automático em silêncios + recolagem sem emenda).
3. **Texto → narração**: TTS realista com a voz escolhida.

Motor primário: ElevenLabs (vozes realistas, multilíngue). Sem chave no cofre, o
fluxo de conversão cai para a cadeia FFmpeg local de mudança de timbre.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

from ..services import ingest, jobs, media, voice_engine
from ..services.delivery import deliver
from ..services.sterilizer import LEVELS, normalize_level
from ..services.validation import (
    AUDIO_EXT,
    VIDEO_EXT,
    ValidationError,
    clean_text,
    output_path,
    parse_json_object,
    save_upload,
)
from ..services.voice_engine import Settings, VoiceEngineError

bp = Blueprint("voice", __name__, url_prefix="/api/voice")

# Presets de timbre do motor local: (pitch em semitons, fator de formante)
VOICES = {
    "masc_grave": (-3.0, 0.94),
    "masc_jovem": (-1.0, 0.98),
    "fem_suave": (3.0, 1.06),
    "fem_energetica": (4.5, 1.08),
    "narrador": (-2.0, 0.96),
}
FORMATS = {"wav": ".wav", "mp3": ".mp3", "aac": ".m4a"}
TIMINGS = ("strict", "natural")
ENGINES = ("elevenlabs", "local")
SAMPLE_RATE = 48000
MEDIA_EXT = AUDIO_EXT | VIDEO_EXT
MAX_TTS_CHARS = 40000


def _settings_from_form() -> Settings:
    def num(name: str, default: float, low: float, high: float) -> float:
        try:
            return max(low, min(high, float(request.form.get(name, default))))
        except (TypeError, ValueError):
            return default

    return Settings(
        stability=num("stability", 0.5, 0.0, 1.0),
        similarity_boost=num("similarity", 0.85, 0.0, 1.0),
        style=num("style", 0.0, 0.0, 1.0),
        speaker_boost=(request.form.get("speaker_boost", "1") not in ("0", "false", "off")),
    )


@bp.get("/catalog")
def catalog():
    return jsonify(
        engine_ready=voice_engine.available(),
        engines=list(ENGINES),
        voices=[
            {"id": vid, "semitones": semi, "formant": formant}
            for vid, (semi, formant) in VOICES.items()
        ],
        realistic_voices=voice_engine.list_voices(),
        formats=list(FORMATS),
        timings=list(TIMINGS),
        levels=list(LEVELS),
        max_tts_chars=MAX_TTS_CHARS,
    )


@bp.get("/voices")
def voices():
    return jsonify(engine_ready=voice_engine.available(), voices=voice_engine.list_voices())


def _common_params() -> tuple[str, str, str]:
    fmt = request.form.get("format", "mp3")
    if fmt not in FORMATS:
        raise ValidationError("Formato de saída inválido.")
    raw_mutation = request.form.get("mutation")
    mutation = normalize_level(raw_mutation)
    if raw_mutation not in (None, "") and mutation is None:
        raise ValidationError("Nível de mutação inválido.")
    preserve = (request.form.get("preserve_timing") or "strict").strip().lower()
    if preserve not in TIMINGS:
        raise ValidationError("Modo de timing inválido.")
    return fmt, (mutation or "leve"), preserve


# --------------------------------------------------------------------------- #
# Conversão de narrador (vídeo ou áudio)
# --------------------------------------------------------------------------- #
@bp.post("/convert")
def convert():
    engine = (request.form.get("engine") or ("elevenlabs" if voice_engine.available() else "local")).lower()
    if engine not in ENGINES:
        return jsonify(error="Motor de voz inválido."), 400

    target = request.form.get("target_voice", "masc_grave")
    realistic_voice = (request.form.get("voice_id") or "").strip()
    keep_video = request.form.get("keep_video", "1") not in ("0", "false", "off")

    if engine == "local" and target not in VOICES:
        return jsonify(error="Timbre alvo inválido."), 400
    if engine == "elevenlabs":
        if not voice_engine.available():
            return jsonify(
                error="Nenhuma chave ElevenLabs configurada. Cadastre em /apis para liberar as vozes realistas."
            ), 400
        if not realistic_voice:
            return jsonify(error="Escolha uma voz realista."), 400

    try:
        fmt, mutation, preserve = _common_params()
        source_card = parse_json_object(request.form.get("source_card"), field="source_card")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    job = jobs.create_job(
        "voice",
        meta={
            "mode": "convert",
            "engine": engine,
            "target": realistic_voice or target,
            "format": fmt,
            "timing": preserve,
            "mutation": mutation,
            "keep_video": keep_video,
            **({"source_card": source_card} if source_card else {}),
        },
    )

    source_url = (request.form.get("url") or "").strip()
    upload = request.files.get("media") or request.files.get("audio") or request.files.get("video")
    src: Path | None = None
    if upload and upload.filename:
        try:
            src = save_upload(upload, job["job_id"], MEDIA_EXT)
        except ValidationError as exc:
            jobs.update(job["job_id"], status="error", message=str(exc))
            return jsonify(error=str(exc)), 400
    elif not ingest.is_supported_url(source_url):
        msg = "Envie um vídeo/áudio ou selecione um conteúdo na pesquisa."
        jobs.update(job["job_id"], status="error", message=msg)
        return jsonify(error=msg), 400

    settings = _settings_from_form()
    jobs.submit(
        job["job_id"],
        lambda jid: _work_convert(
            jid, src, engine, target, realistic_voice, fmt, mutation, preserve, source_url, keep_video, settings
        ),
    )
    return jsonify(job), 202


# --------------------------------------------------------------------------- #
# Texto → narração
# --------------------------------------------------------------------------- #
@bp.post("/tts")
def tts():
    if not voice_engine.available():
        return jsonify(
            error="Narração por texto exige a chave ElevenLabs. Cadastre em /apis (provedor ElevenLabs)."
        ), 400

    voice_id = (request.form.get("voice_id") or "").strip()
    if not voice_id:
        return jsonify(error="Escolha uma voz para a narração."), 400

    try:
        text = clean_text(request.form.get("text"), max_length=MAX_TTS_CHARS, field="text")
        fmt, mutation, _preserve = _common_params()
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    if len(text) < 2:
        return jsonify(error="Escreva o roteiro que será narrado."), 400

    try:
        speed = max(0.7, min(1.2, float(request.form.get("speed", 1.0))))
    except (TypeError, ValueError):
        speed = 1.0

    job = jobs.create_job(
        "voice",
        meta={
            "mode": "tts",
            "engine": "elevenlabs",
            "target": voice_id,
            "format": fmt,
            "mutation": mutation,
            "chars": len(text),
        },
    )
    settings = _settings_from_form()
    jobs.submit(job["job_id"], lambda jid: _work_tts(jid, text, voice_id, fmt, mutation, speed, settings))
    return jsonify(job), 202


# --------------------------------------------------------------------------- #
# Motor local (fallback FFmpeg)
# --------------------------------------------------------------------------- #
def build_timbre_chain(target: str, timing: str) -> list[str]:
    """Cadeia FFmpeg que troca o timbre e devolve (ou não) a duração original."""
    semitones, formant = VOICES[target]
    ratio = 2 ** (semitones / 12)
    tempo = (1 / ratio) if timing == "strict" else (1 / ratio) * 0.98
    return [
        f"asetrate={int(SAMPLE_RATE * ratio)}",
        f"aresample={SAMPLE_RATE}",
        f"atempo={tempo:.6f}",
        f"equalizer=f=2500:width_type=h:width=1200:g={(formant - 1) * 12:.2f}",
        "dynaudnorm=f=200:g=5",
    ]


# --------------------------------------------------------------------------- #
# Workers
# --------------------------------------------------------------------------- #
def _work_convert(
    job_id: str,
    src: Path | None,
    engine: str,
    target: str,
    voice_id: str,
    fmt: str,
    mutation: str,
    timing: str,
    source_url: str,
    keep_video: bool,
    settings: Settings,
) -> None:
    src = ingest.resolve_source(src, source_url, job_id)
    info = media.probe(src)
    if not info.has_audio:
        raise RuntimeError("O arquivo enviado não tem trilha de áudio para converter.")

    jobs.update(job_id, progress=15)

    if engine == "local":
        jobs.log(
            job_id,
            f"Motor local · timbre '{target}' · timing {timing} · {info.duration:.1f}s de áudio",
        )
        dst = output_path("voice", job_id, FORMATS[fmt])
        report = media.sterilize(
            src, dst, job_id=job_id, level=mutation,
            extra_audio_filters=build_timbre_chain(target, timing), audio_only=True,
        )
        src.unlink(missing_ok=True)
        deliver(job_id, dst, report, message="Voz convertida no motor local e áudio sem rastro.")
        return

    work_dir = output_path("voice", job_id, ".tmp").parent
    converted = work_dir / f"{job_id}_voice.wav"
    try:
        voice_engine.speech_to_speech(
            src, converted,
            voice_id=voice_id, job_id=job_id, settings=settings, keep_timing=(timing == "strict"),
        )
    except VoiceEngineError as exc:
        raise RuntimeError(str(exc)) from exc

    jobs.update(job_id, progress=88)

    if keep_video and info.has_video:
        muxed = work_dir / f"{job_id}_muxed.mp4"
        voice_engine.swap_video_audio(src, converted, muxed, job_id)
        dst = output_path("voice", job_id, ".mp4")
        report = media.sterilize(muxed, dst, job_id=job_id, level=mutation)
        muxed.unlink(missing_ok=True)
        message = "Narrador trocado, vídeo remuxado e arquivo esterilizado."
    else:
        dst = output_path("voice", job_id, FORMATS[fmt])
        report = media.sterilize(converted, dst, job_id=job_id, level=mutation, audio_only=True)
        message = "Narrador trocado com narrativa e timing preservados."

    converted.unlink(missing_ok=True)
    src.unlink(missing_ok=True)
    deliver(job_id, dst, report, message=message)


def _work_tts(
    job_id: str,
    text: str,
    voice_id: str,
    fmt: str,
    mutation: str,
    speed: float,
    settings: Settings,
) -> None:
    jobs.update(job_id, progress=12)
    work_dir = output_path("voice", job_id, ".tmp").parent
    narrated = work_dir / f"{job_id}_tts.wav"
    try:
        voice_engine.text_to_speech(
            text, narrated, voice_id=voice_id, job_id=job_id, settings=settings, speed=speed
        )
    except VoiceEngineError as exc:
        raise RuntimeError(str(exc)) from exc

    jobs.update(job_id, progress=90)
    dst = output_path("voice", job_id, FORMATS[fmt])
    report = media.sterilize(narrated, dst, job_id=job_id, level=mutation, audio_only=True)
    narrated.unlink(missing_ok=True)
    duration = media.probe_duration(dst)
    deliver(
        job_id, dst, report,
        message=f"Narração gerada ({duration/60:.1f} min) com voz realista e áudio sem rastro.",
    )
