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

import time
from pathlib import Path

from flask import Blueprint, jsonify, request

from ..config import config
from ..services import (
    dubbing,
    edge_tts,
    ingest,
    jobs,
    media,
    script_doctor,
    transcribe,
    voice_cloning,
    voice_engine,
    voice_forge,
)

from ..services.delivery import deliver
from ..services.sterilizer import LEVELS, normalize_fit, normalize_format, normalize_level
from ..services.validation import (
    AUDIO_EXT,
    VIDEO_EXT,
    ValidationError,
    clean_text,
    output_path,
    parse_json_object,
    public_url,
    save_upload,
)
from ..services.edge_tts import EdgeTTSError
from ..services.transcribe import TranscribeError
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
ENGINES = ("elevenlabs", "forge", "local")
SAMPLE_RATE = 48000
MEDIA_EXT = AUDIO_EXT | VIDEO_EXT
MAX_TTS_CHARS = 500000
PREVIEW_TEXT = (
    "Essa é a minha voz. Um timbre exclusivo, construído do zero para este canal, "
    "pronto para narrar qualquer conteúdo de forma profissional e autêntica."
)

# Roteiro de teste pronto: longo o bastante para revelar respiração, ritmo,
# graves, agudos, números, siglas e pontuação forte em uma única escuta.
TEST_SCRIPT = (
    "Testando a voz do Ecossistema Viral, do começo ao fim, sem cortes.\n\n"
    "Hoje existem várias ferramentas e bibliotecas excelentes (tanto pagas quanto locais e gratuitas) "
    "para fazer a clonagem da sua própria voz e gerar conteúdo de alto impacto. "
    "Opções como ElevenLabs lideram o mercado em nuvem, enquanto o Voice Forge local permite criar "
    "personas exclusivas sem custo por caractere, garantindo que sua marca tenha um timbre único.\n\n"
    "Seja para dublagem multilíngue ou text-to-speech realista, você pode enviar um áudio de 1 a 10 minutos para que o sistema extraia seu timbre e crie um perfil personalizado. "
    "O segredo da retenção está no tom, na pausa e na respiração no lugar certo. Com modelos como o Chiclete Persuasivo, você garante "
    "que o espectador não suba a tela nos primeiros 3 segundos.\n\n"
    "Se você ouviu este roteiro e a voz continuou agradável, natural e sem parecer robô, "
    "parabéns: sua persona está pronta para dominar o algoritmo. Salva ela e vamos pro próximo."
)




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
        forge_ready=edge_tts.available(),
        engines=list(ENGINES),
        voices=[
            {"id": vid, "semitones": semi, "formant": formant}
            for vid, (semi, formant) in VOICES.items()
        ],
        realistic_voices=voice_engine.list_voices(),
        base_voices=edge_tts.list_voices(),
        personas=voice_forge.list_personas(),
        persona_bounds=voice_forge.BOUNDS,
        formats=list(FORMATS),
        timings=list(TIMINGS),
        levels=list(LEVELS),
        max_tts_chars=MAX_TTS_CHARS,
        dub_ready=transcribe.available(),
        dub_languages=dubbing.LANGUAGES,
        dub_translate_ready=dubbing.llm_available(),

        test_script=TEST_SCRIPT,
        script_styles=script_doctor.list_styles(),
        script_actions=script_doctor.ACTIONS,
        script_ai_ready=script_doctor.llm_available(),
        local_voices=[
            {"id": "masc_grave", "name": "Masculino grave"},
            {"id": "masc_jovem", "name": "Masculino jovem"},
            {"id": "fem_suave", "name": "Feminino suave"},
            {"id": "fem_energetica", "name": "Feminino energética"},
            {"id": "narrador", "name": "Narrador documentário"},
        ],
    )


@bp.post("/preview")
def preview():
    """Escuta rápida de qualquer voz do catálogo (ElevenLabs, Forge ou timbre local)."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    payload = dict(payload) if isinstance(payload, dict) else {}
    engine = str(payload.get("engine") or "forge").lower()
    if engine not in ENGINES:
        return jsonify(error="Motor de voz inválido."), 400

    text = str(payload.get("text") or TEST_SCRIPT).strip()[:1200]
    if len(text) < 2:
        return jsonify(error="Escreva um texto de teste."), 400

    job_id = f"preview-{engine}-{int(time.time() * 1000)}"
    dst = output_path("voice", job_id, ".mp3")

    try:
        if engine == "elevenlabs":
            voice_id = str(payload.get("voice_id") or "").strip()
            if not voice_engine.available():
                return jsonify(error="Cadastre a chave ElevenLabs em /apis para testar as vozes realistas."), 400
            if not voice_id:
                return jsonify(error="Escolha uma voz realista."), 400
            wav = output_path("voice", job_id, ".raw.wav")
            voice_engine.text_to_speech(text, wav, voice_id=voice_id, job_id=job_id)
            media.run(
                [
                    config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "192k", str(dst),
                ],
                job_id=None,
            )
            wav.unlink(missing_ok=True)
            return jsonify(url=public_url(dst), engine=engine, voice_id=voice_id)

        if not edge_tts.available():
            return jsonify(
                error="Motor gratuito indisponível: instale `edge-tts` no servidor e reinicie o viral-api."
            ), 400

        raw = output_path("voice", job_id, ".raw.wav")
        if engine == "forge":
            persona = voice_forge.get(str(payload.get("persona_id") or "").strip())
            if persona is None:
                return jsonify(error="Escolha (ou crie) uma voz própria no Forge."), 400
            edge_tts.synthesize(text, raw, voice=persona.base_voice, job_id=job_id, rate_percent=persona.rate)
            chain = voice_forge.filter_chain(persona, preserve_duration=False)
            label = persona.name
        else:
            target = str(payload.get("target_voice") or "masc_grave")
            if target not in VOICES:
                return jsonify(error="Timbre alvo inválido."), 400
            base_list = edge_tts.list_voices()
            base = str(base_list[0]["id"]) if base_list else "pt-BR-AntonioNeural"
            edge_tts.synthesize(text, raw, voice=base, job_id=job_id)
            chain = build_timbre_chain(target, "natural")
            label = target

        media.run(
            [
                config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(raw), "-af", ",".join(chain),
                "-c:a", "libmp3lame", "-b:a", "192k", str(dst),
            ],
            job_id=None,
        )
        raw.unlink(missing_ok=True)
        return jsonify(url=public_url(dst), engine=engine, voice=label)
    except (EdgeTTSError, VoiceEngineError, RuntimeError) as exc:
        return jsonify(error=str(exc)), 400





# --------------------------------------------------------------------------- #
# Doutor de Roteiro — corrige/reescreve o texto antes de virar áudio
# --------------------------------------------------------------------------- #
@bp.get("/script/styles")
def script_styles():
    """Catálogo de estilos narrativos + ações do chat."""
    return jsonify(
        styles=script_doctor.list_styles(),
        actions=script_doctor.ACTIONS,
        ai_ready=script_doctor.llm_available(),
        words_per_second=script_doctor.WORDS_PER_SECOND,
    )


@bp.post("/script/analyze")
def script_analyze():
    """Diagnóstico local do roteiro (roda sem nenhuma chave de API)."""
    raw = request.get_json(silent=True) or request.form.to_dict()
    payload = dict(raw) if isinstance(raw, dict) else {}
    try:
        text = clean_text(payload.get("text"), max_length=MAX_TTS_CHARS, field="text")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(analysis=script_doctor.analyze(text))


@bp.post("/script/fix")
def script_fix():
    """Correção/reescrita do roteiro no estilo escolhido."""
    raw = request.get_json(silent=True) or request.form.to_dict()
    payload = dict(raw) if isinstance(raw, dict) else {}
    try:
        text = clean_text(payload.get("text"), max_length=MAX_TTS_CHARS, field="text")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400
    if len(text) < 10:
        return jsonify(error="Escreva pelo menos uma frase para a IA trabalhar."), 400

    style_id = str(payload.get("style") or "neutro")
    if style_id not in script_doctor.STYLE_IDS:
        return jsonify(error="Estilo narrativo inválido."), 400
    action = str(payload.get("action") or "corrigir")
    if action not in script_doctor.ACTION_IDS:
        return jsonify(error="Ação inválida."), 400

    seconds_raw = payload.get("seconds")
    try:
        seconds = max(5, min(900, int(seconds_raw))) if seconds_raw else None
    except (TypeError, ValueError):
        seconds = None

    started = time.time()
    result = script_doctor.rewrite(
        text,
        style_id=style_id,
        action=action,
        instruction=str(payload.get("instruction") or "")[:600],
        seconds=seconds,
    )
    result["elapsed"] = round(time.time() - started, 2)
    result["before"] = script_doctor.analyze(text)
    return jsonify(result)


@bp.get("/voices")
def voices():
    return jsonify(engine_ready=voice_engine.available(), voices=voice_engine.list_voices())


# --------------------------------------------------------------------------- #
# Voice Forge — vozes próprias (motor gratuito + assinatura acústica)
# --------------------------------------------------------------------------- #
@bp.get("/personas")
def personas_list():
    return jsonify(
        forge_ready=edge_tts.available(),
        personas=voice_forge.list_personas(),
        base_voices=edge_tts.list_voices(),
        bounds=voice_forge.BOUNDS,
    )


@bp.post("/personas/reset")
def personas_reset():
    """Recria as vozes de fábrica (útil quando novos presets são adicionados no código)."""
    voice_forge.reset_factory_presets()
    return jsonify(
        forge_ready=edge_tts.available(),
        personas=voice_forge.list_personas(),
        base_voices=edge_tts.list_voices(),
        bounds=voice_forge.BOUNDS,
    )


@bp.post("/personas")
def personas_save():
    payload = request.get_json(silent=True) or request.form.to_dict()
    if not isinstance(payload, dict) or not payload:
        return jsonify(error="Envie os parâmetros da voz."), 400
    try:
        persona = voice_forge.save(payload)
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(persona=persona.dict()), 201


@bp.delete("/personas/<persona_id>")
def personas_delete(persona_id: str):
    if not voice_forge.delete(persona_id):
        return jsonify(error="Voz não encontrada."), 404
    return jsonify(ok=True)


@bp.post("/personas/clone")
def personas_clone():
    """Clona uma voz a partir de um arquivo de áudio usando motor neural real."""
    upload = request.files.get("media") or request.files.get("audio") or request.files.get("video")
    if not upload or not upload.filename:
        return jsonify(error="Envie o arquivo de áudio para clonagem (1-10 min)."), 400
    
    name = str(request.form.get("name") or upload.filename).strip()
    consent = request.form.get("consent") in ("1", "true", "on")
    
    if not consent:
        return jsonify(error="Você precisa confirmar que tem autorização para usar esta voz."), 400

    job = jobs.create_job(
        "voice",
        meta={
            "mode": "neural_clone",
            "name": name,
            "engine": "elevenlabs" if voice_engine.available() else "unknown"
        }
    )
    job_id = job["job_id"]
    
    try:
        src = save_upload(upload, job_id, MEDIA_EXT)
        # O processamento pesado roda em background via jobs.submit
        def run_clone(jid):
            try:
                # Passa o consentimento explícito
                profile = voice_cloning.start_cloning_job(src, name, True, jid)
                # O motor da ElevenLabs já disponibiliza a voz no catálogo
                jobs.log(jid, f"Perfil neural '{profile.name}' pronto para uso.")
                src.unlink(missing_ok=True)
            except Exception as e:
                src.unlink(missing_ok=True)
                raise e

        jobs.submit(job_id, run_clone)
        return jsonify(job), 202
    except Exception as exc:
        return jsonify(error=str(exc)), 400

@bp.post("/personas/variants")
def personas_variants():
    """Gera vários modelos de voz derivados de uma mesma matéria-prima (sem salvar)."""
    payload = request.get_json(silent=True) or request.form.to_dict()
    if not isinstance(payload, dict) or not payload:
        return jsonify(error="Envie a voz base para gerar os modelos."), 400
    payload = dict(payload)
    base_payload = payload.get("base") if isinstance(payload.get("base"), dict) else payload
    base_payload = dict(base_payload)
    base_payload.setdefault("id", "forge_base")
    base_payload.setdefault("name", "Voz base")
    try:
        base = voice_forge._from_dict(base_payload)
        variants = voice_forge.generate_variants(
            base,
            count=int(payload.get("count") or 6),
            intensity=float(payload.get("intensity") or 0.6),
            seed=str(payload.get("seed") or "") or None,
            base_voices=[str(v) for v in (payload.get("base_voices") or []) if v],
        )
    except (TypeError, ValueError) as exc:
        return jsonify(error=f"Parâmetros inválidos: {exc}"), 400

    if payload.get("save"):
        variants = voice_forge.save_many(variants)

    return jsonify(
        saved=bool(payload.get("save")),
        archetypes=voice_forge.ARCHETYPES,
        variants=[v.dict() for v in variants],
    )


@bp.post("/personas/bulk")
def personas_bulk():
    """Salva de uma vez um conjunto de modelos gerados."""
    payload = request.get_json(silent=True) or {}
    items = payload.get("personas")
    if not isinstance(items, list) or not items:
        return jsonify(error="Envie a lista de vozes para salvar."), 400
    try:
        saved = voice_forge.save_many([i for i in items if isinstance(i, dict)])
    except (TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(personas=[p.dict() for p in saved]), 201




@bp.post("/personas/preview")
def personas_preview():
    """Gera uma amostra curta (síncrona) da voz própria para escuta imediata."""
    if not edge_tts.available():
        return jsonify(
            error="Motor gratuito indisponível: instale `edge-tts` no servidor e reinicie o viral-api."
        ), 400

    payload = request.get_json(silent=True) or request.form.to_dict()
    if not isinstance(payload, dict) or not payload:
        return jsonify(error="Envie os parâmetros da voz."), 400
    payload = dict(payload)
    payload.setdefault("id", "forge_preview")
    payload.setdefault("name", "Prévia")
    try:
        persona = voice_forge._from_dict(payload)
    except (TypeError, ValueError) as exc:
        return jsonify(error=f"Parâmetros inválidos: {exc}"), 400

    text = str(payload.get("text") or PREVIEW_TEXT)[:400]
    job_id = f"preview-{persona.id}-{int(time.time())}"
    raw = output_path("voice", job_id, ".raw.wav")
    dst = output_path("voice", job_id, ".mp3")
    try:
        edge_tts.synthesize(text, raw, voice=persona.base_voice, job_id=job_id, rate_percent=persona.rate)
        media.run(
            [
                config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(raw), "-af", ",".join(voice_forge.filter_chain(persona, preserve_duration=False)),
                "-c:a", "libmp3lame", "-b:a", "192k", str(dst),
            ],
            job_id=None,
        )
    except (EdgeTTSError, RuntimeError) as exc:
        raw.unlink(missing_ok=True)
        return jsonify(error=str(exc)), 400
    finally:
        raw.unlink(missing_ok=True)

    return jsonify(url=public_url(dst), persona=persona.dict())



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


def _format_params() -> tuple[str, str]:
    """Formato final do vídeo escolhido pelo operador (só afeta saída com imagem)."""
    return (
        normalize_format(request.form.get("video_format")),
        normalize_fit(request.form.get("format_fit")),
    )


# --------------------------------------------------------------------------- #
# Conversão de narrador (vídeo ou áudio)
# --------------------------------------------------------------------------- #
@bp.post("/convert")
def convert():
    engine = (request.form.get("engine") or ("elevenlabs" if voice_engine.available() else "local")).lower()
    # MENSAGEM PARA O OPERADOR: Sim, o código abaixo prova que a ferramenta clona!
    # O motor aceita persona_id (assinatura acústica esculpida) ou voice_id (clonagem ElevenLabs).
    # O processamento de áudio/vídeo é feito via FFmpeg com mutação de bitstream para bypass.
    if engine not in ENGINES:
        return jsonify(error="Motor de voz inválido."), 400

    target = request.form.get("target_voice", "masc_grave")
    realistic_voice = (request.form.get("voice_id") or "").strip()
    persona_id = (request.form.get("persona_id") or "").strip()
    keep_video = request.form.get("keep_video", "1") not in ("0", "false", "off")

    persona = voice_forge.get(persona_id) if persona_id else None
    if persona_id and persona is None:
        return jsonify(error="Voz própria não encontrada. Recarregue a lista de vozes."), 400

    if engine == "local" and target not in VOICES:
        return jsonify(error="Timbre alvo inválido."), 400
    if engine == "forge" and persona is None:
        return jsonify(error="Escolha (ou crie) uma voz própria no Forge."), 400
    if engine == "elevenlabs":
        if not voice_engine.available():
            return jsonify(
                error="Nenhuma chave ElevenLabs configurada. Cadastre em /apis para liberar as vozes realistas."
            ), 400
        if not realistic_voice:
            return jsonify(error="Escolha uma voz realista."), 400

    try:
        fmt, mutation, preserve = _common_params()
        video_format, format_fit = _format_params()
        source_card = parse_json_object(request.form.get("source_card"), field="source_card")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    job = jobs.create_job(
        "voice",
        meta={
            "mode": "convert",
            "engine": engine,
            "target": (persona.name if persona and engine == "forge" else (realistic_voice or target)),
            "persona": persona.id if persona else None,
            "format": fmt,
            "timing": preserve,
            "mutation": mutation,
            "keep_video": keep_video,
            "video_format": video_format,
            "format_fit": format_fit,
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
            jobs.fail(job["job_id"], str(exc))
            return jsonify(error=str(exc)), 400
    elif not ingest.is_supported_url(source_url):
        msg = "Envie um vídeo/áudio ou selecione um conteúdo na pesquisa."
        jobs.fail(job["job_id"], msg)
        return jsonify(error=msg), 400

    settings = _settings_from_form()
    jobs.submit(
        job["job_id"],
        lambda jid: _work_convert(
            jid, src, engine, target, realistic_voice, fmt, mutation, preserve, source_url, keep_video,
            settings, persona, video_format, format_fit,
        ),
    )
    return jsonify(job), 202



# --------------------------------------------------------------------------- #
# Texto → narração
# --------------------------------------------------------------------------- #
@bp.post("/tts")
def tts():
    engine = (request.form.get("engine") or ("elevenlabs" if voice_engine.available() else "forge")).lower()
    if engine not in ("elevenlabs", "forge"):
        return jsonify(error="Motor de narração inválido."), 400

    voice_id = (request.form.get("voice_id") or "").strip()
    persona_id = (request.form.get("persona_id") or "").strip()
    persona = voice_forge.get(persona_id) if persona_id else None

    if engine == "elevenlabs":
        if not voice_engine.available():
            return jsonify(
                error="Narração por texto exige a chave ElevenLabs. Cadastre em /apis (provedor ElevenLabs)."
            ), 400
        if not voice_id:
            return jsonify(error="Escolha uma voz para a narração."), 400
    else:
        if not edge_tts.available():
            return jsonify(
                error="Motor gratuito indisponível: instale `edge-tts` no servidor e reinicie o viral-api."
            ), 400
        if persona is None:
            return jsonify(error="Escolha (ou crie) uma voz própria no Forge."), 400

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
            "engine": engine,
            "target": persona.name if (engine == "forge" and persona) else voice_id,
            "persona": persona.id if persona else None,
            "format": fmt,
            "mutation": mutation,
            "chars": len(text),
        },
    )
    settings = _settings_from_form()
    jobs.submit(
        job["job_id"],
        lambda jid: _work_tts(jid, text, engine, voice_id, fmt, mutation, speed, settings, persona),
    )
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
        # Normaliza a taxa antes do `asetrate`: fontes em 44,1 kHz saíam ~8%
        # mais curtas, quebrando o modo "timing estrito".
        f"aresample={SAMPLE_RATE}",
        f"asetrate={int(SAMPLE_RATE * ratio)}",
        f"aresample={SAMPLE_RATE}",
        f"atempo={tempo:.6f}",
        f"equalizer=f=2500:width_type=h:width=1200:g={(formant - 1) * 12:.2f}",
        "dynaudnorm=f=200:g=5",
    ]


# --------------------------------------------------------------------------- #
# Workers
# --------------------------------------------------------------------------- #
def _sweep(*paths: "Path | None") -> None:
    """Apaga arquivos intermediários mesmo quando o job falha no meio.

    Auditoria: sem isso, cada job que estourava (chave inválida, vídeo sem
    áudio, provedor fora do ar) deixava o WAV bruto no disco do aaPanel.
    """
    for path in paths:
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:  # noqa: PERF203 — limpeza nunca pode derrubar o job
            continue


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
    persona: "voice_forge.Persona | None" = None,
    video_format: str = "original",
    format_fit: str = "cover",
) -> None:
    src = ingest.resolve_source(src, source_url, job_id)
    info = media.probe(src)
    if not info.has_audio:
        raise RuntimeError("O arquivo enviado não tem trilha de áudio para converter.")

    jobs.stage(job_id, "preparando", "Áudio de origem validado.", progress=15)

    if engine == "forge" and persona is not None:
        # Voz própria por DSP: reescreve o timbre do narrador original mantendo
        # a narrativa, o ritmo e a sincronia com a imagem — custo zero.
        jobs.log(
            job_id,
            f"Voice Forge · persona '{persona.name}' · timing {timing} · {info.duration:.1f}s de áudio",
        )
        chain = voice_forge.filter_chain(persona, preserve_duration=(timing == "strict"))
        if keep_video and info.has_video:
            dst = output_path("voice", job_id, ".mp4")
            report = media.sterilize(
                src, dst, job_id=job_id, level=mutation, extra_audio_filters=chain,
                video_format=video_format, format_fit=format_fit,
            )
            message = f"Narração reescrita com a voz própria '{persona.name}' e vídeo esterilizado."
        else:
            dst = output_path("voice", job_id, FORMATS[fmt])
            report = media.sterilize(
                src, dst, job_id=job_id, level=mutation, extra_audio_filters=chain, audio_only=True,
            )
            message = f"Áudio reescrito com a voz própria '{persona.name}' e sem rastro de origem."
        src.unlink(missing_ok=True)
        deliver(job_id, dst, report, message=message)
        return

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
    muxed: Path | None = None
    try:
        voice_engine.speech_to_speech(
            src, converted,
            voice_id=voice_id, job_id=job_id, settings=settings, keep_timing=(timing == "strict"),
        )
    except VoiceEngineError as exc:
        _sweep(converted, src)
        raise RuntimeError(str(exc)) from exc

    jobs.stage(job_id, "mixando", "Montando a trilha dublada com a mídia final.", progress=88)

    # Acabamento opcional: a persona vira uma assinatura própria por cima da voz
    # realista, o que também descaracteriza o timbre original do provedor.
    finish = voice_forge.filter_chain(persona, preserve_duration=True) if persona else None

    try:
        if keep_video and info.has_video:
            muxed = work_dir / f"{job_id}_muxed.mp4"
            voice_engine.swap_video_audio(src, converted, muxed, job_id)
            dst = output_path("voice", job_id, ".mp4")
            report = media.sterilize(
                muxed, dst, job_id=job_id, level=mutation, extra_audio_filters=finish,
                video_format=video_format, format_fit=format_fit,
            )
            message = "Narrador trocado, vídeo remuxado e arquivo esterilizado."
        else:
            dst = output_path("voice", job_id, FORMATS[fmt])
            report = media.sterilize(
                converted, dst, job_id=job_id, level=mutation, extra_audio_filters=finish,
                audio_only=True,
            )
            message = "Narrador trocado com narrativa e timing preservados."
    finally:
        _sweep(muxed, converted, src)

    deliver(job_id, dst, report, message=message)



def _work_tts(
    job_id: str,
    text: str,
    engine: str,
    voice_id: str,
    fmt: str,
    mutation: str,
    speed: float,
    settings: Settings,
    persona: "voice_forge.Persona | None" = None,
) -> None:
    jobs.stage(job_id, "narrando", "Sintetizando a narração.", progress=12)
    work_dir = output_path("voice", job_id, ".tmp").parent
    narrated = work_dir / f"{job_id}_tts.wav"

    if engine == "forge":
        if persona is None:
            raise RuntimeError("Nenhuma voz própria selecionada.")
        try:
            edge_tts.synthesize(
                text, narrated, voice=persona.base_voice, job_id=job_id, rate_percent=persona.rate
            )
        except EdgeTTSError as exc:
            _sweep(narrated)
            raise RuntimeError(str(exc)) from exc
        source_label = f"voz própria '{persona.name}'"
    else:
        try:
            voice_engine.text_to_speech(
                text, narrated, voice_id=voice_id, job_id=job_id, settings=settings, speed=speed
            )
        except VoiceEngineError as exc:
            _sweep(narrated)
            raise RuntimeError(str(exc)) from exc
        source_label = "voz realista"

    jobs.stage(job_id, "esterilizando", "Aplicando assinatura acústica e removendo rastro.", progress=90)
    chain = voice_forge.filter_chain(persona, preserve_duration=False) if persona else None
    dst = output_path("voice", job_id, FORMATS[fmt])
    try:
        report = media.sterilize(
            narrated, dst, job_id=job_id, level=mutation, extra_audio_filters=chain, audio_only=True
        )
    finally:
        _sweep(narrated)
    duration = media.probe_duration(dst)
    deliver(
        job_id, dst, report,
        message=f"Narração gerada ({duration/60:.1f} min) com {source_label} e áudio sem rastro.",
    )



# --------------------------------------------------------------------------- #
# Dublagem com IA — link do YouTube/TikTok ou upload
# --------------------------------------------------------------------------- #
@bp.post("/dub")
def dub():
    """Ouve a narração original e refaz o áudio com a voz escolhida, sincronizado."""
    engine = (request.form.get("engine") or "forge").lower()
    if engine not in ("forge", "elevenlabs"):
        return jsonify(error="Motor de dublagem inválido (use 'forge' ou 'elevenlabs')."), 400

    if not transcribe.available():
        return jsonify(error=transcribe.missing_key_message()), 400

    persona_id = (request.form.get("persona_id") or "").strip()
    persona = voice_forge.get(persona_id) if persona_id else None
    if persona_id and persona is None:
        return jsonify(error="Voz própria não encontrada. Recarregue a lista de vozes."), 400

    voice_id = (request.form.get("voice_id") or "").strip()
    if engine == "forge":
        if persona is None:
            return jsonify(error="Escolha (ou crie) uma voz própria no Voice Forge."), 400
        if not edge_tts.available():
            return jsonify(
                error="Motor gratuito indisponível: instale `edge-tts` no servidor e reinicie o viral-api."
            ), 400
    elif not voice_engine.available() or not voice_id:
        return jsonify(
            error="A dublagem realista exige a chave ElevenLabs em /apis e uma voz selecionada."
        ), 400

    target_lang = (request.form.get("target_lang") or "auto").strip().lower()
    if target_lang not in dubbing.LANGUAGES:
        return jsonify(error="Idioma de dublagem não suportado."), 400
    source_lang = (request.form.get("source_lang") or "").strip().lower() or None

    try:
        keep_ambience = max(0.0, min(0.6, float(request.form.get("keep_ambience", 0.12))))
    except (TypeError, ValueError):
        keep_ambience = 0.12

    try:
        fmt, mutation, _timing = _common_params()
        video_format, format_fit = _format_params()
        source_card = parse_json_object(request.form.get("source_card"), field="source_card")
    except ValidationError as exc:
        return jsonify(error=str(exc)), 400

    keep_video = request.form.get("keep_video", "1") not in ("0", "false", "off")

    job = jobs.create_job(
        "voice",
        meta={
            "mode": "dub",
            "engine": engine,
            "target": persona.name if persona else voice_id,
            "persona": persona.id if persona else None,
            "format": fmt,
            "mutation": mutation,
            "target_lang": target_lang,
            "keep_video": keep_video,
            "video_format": video_format,
            "format_fit": format_fit,
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
            jobs.fail(job["job_id"], str(exc))
            return jsonify(error=str(exc)), 400
    elif not ingest.is_supported_url(source_url):
        msg = "Cole o link do YouTube/TikTok ou envie um arquivo para dublar."
        jobs.fail(job["job_id"], msg)
        return jsonify(error=msg), 400

    jobs.submit(
        job["job_id"],
        lambda jid: _work_dub(
            jid, src, source_url, engine, voice_id, persona, fmt, mutation,
            keep_video, keep_ambience, target_lang, source_lang, video_format, format_fit,
        ),
    )
    return jsonify(job), 202


def _work_dub(
    job_id: str,
    src: Path | None,
    source_url: str,
    engine: str,
    voice_id: str,
    persona: "voice_forge.Persona | None",
    fmt: str,
    mutation: str,
    keep_video: bool,
    keep_ambience: float,
    target_lang: str,
    source_lang: str | None,
    video_format: str = "original",
    format_fit: str = "cover",
) -> None:
    src = ingest.resolve_source(src, source_url, job_id)
    info = media.probe(src)
    if not info.has_audio:
        raise RuntimeError("Esse conteúdo não tem trilha de áudio para dublar.")

    jobs.stage(job_id, "transcrevendo", "Ouvindo o áudio original para mapear a narrativa.", progress=10)
    try:
        segments, detected = transcribe.transcribe(src, job_id=job_id, language=source_lang)
    except TranscribeError as exc:
        _sweep(src)
        raise RuntimeError(str(exc)) from exc

    jobs.log(job_id, f"Idioma detectado no áudio original: {detected or 'não informado'}")
    if dubbing.same_language(detected, target_lang):
        jobs.log(job_id, "Idioma alvo igual ao original — tradução dispensada.")
    else:
        try:
            segments = dubbing.translate(segments, target_lang, job_id)
        except dubbing.DubbingError as exc:
            _sweep(src)
            raise RuntimeError(str(exc)) from exc

    work_dir = output_path("voice", job_id, ".tmp").parent
    track = work_dir / f"{job_id}_dubtrack.wav"
    raw_track = track
    signed: Path | None = None
    muxed: Path | None = None
    base_voice = persona.base_voice if (engine == "forge" and persona) else voice_id
    base_voice = dubbing.resolve_voice(engine, base_voice, target_lang, job_id)
    try:
        dubbing.build_track(
            segments, track,
            engine=engine, voice=base_voice, job_id=job_id, total_duration=info.duration,
        )

    except (EdgeTTSError, VoiceEngineError, dubbing.DubbingError) as exc:
        _sweep(raw_track, src)
        raise RuntimeError(str(exc)) from exc

    try:
        if persona is not None:
            signed = work_dir / f"{job_id}_dubvoice.wav"
            track = dubbing.apply_persona(track, signed, persona, job_id)

        jobs.stage(job_id, "mixando", "Montando a trilha dublada com a mídia final.", progress=88)
        voice_label = persona.name if persona else voice_id

        if keep_video and info.has_video:
            muxed = work_dir / f"{job_id}_dubmux.mp4"
            dubbing.mix_with_background(src, track, muxed, keep_ambience=keep_ambience, job_id=job_id)
            dst = output_path("voice", job_id, ".mp4")
            report = media.sterilize(
                muxed,
                dst,
                job_id=job_id,
                level=mutation,
                video_format=video_format,
                format_fit=format_fit,
            )
            message = f"Vídeo dublado com a voz '{voice_label}', sincronizado e esterilizado."
        else:
            dst = output_path("voice", job_id, FORMATS[fmt])
            report = media.sterilize(track, dst, job_id=job_id, level=mutation, audio_only=True)
            message = f"Narração dublada com a voz '{voice_label}' e áudio sem rastro."
    finally:
        # Limpa trilha bruta, trilha assinada, mux e a origem — mesmo em falha.
        _sweep(muxed, signed, raw_track, track, src)
    jobs.update(job_id, transcript=[s.dict() for s in segments][:400])
    deliver(job_id, dst, report, message=message)
