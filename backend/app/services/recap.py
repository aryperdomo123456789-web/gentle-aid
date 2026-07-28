"""Recap narrado — o motor que assiste ao vídeo e reconta a história.

Fluxo completo (upload ou link público):

1. **Ouvir** — `transcribe.py` devolve a fala com timestamps.
2. **Ver** — frames amostrados ao longo do vídeo são descritos por um modelo
   multimodal (Gemini, com OpenRouter como rota alternativa). É isso que salva
   cena de ação, terror e novela, onde quase não há diálogo.
3. **Entender** — um LLM lê fala + cenas e devolve nicho, tom, personagens e o
   arco da história em atos, já com os momentos que valem a pena mostrar.
4. **Escrever** — o roteiro de narração nasce ancorado em timestamps reais do
   vídeo e recebe os blocos fixos do operador (abertura, meio e fecho).
5. **Narrar** — cada bloco vira áudio com a voz escolhida (Voice Forge sobre
   Edge TTS, ou ElevenLabs) e a assinatura acústica da persona.
6. **Montar** — para cada bloco o trecho de origem é recortado exatamente na
   duração da narração, reenquadrado no formato pedido e mixado com a trilha
   original abaixada. Legenda animada é opcional.

Uso pretendido: conteúdo do próprio operador ou recap comentado. O motor não
tem nenhum caminho para catálogo de streaming — só upload e link público, igual
às outras esteiras do ecossistema.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import config
from . import api_keys, edge_tts, jobs, media, script_doctor, voice_engine, voice_forge
from .transcribe import Segment

SAMPLE_RATE = 48000

# --------------------------------------------------------------------------- #
# Formatos de saída
# --------------------------------------------------------------------------- #
FORMATS: dict[str, dict[str, Any]] = {
    "short": {
        "id": "short",
        "label": "Recap curto 9:16",
        "hint": "Shorts, Reels e TikTok. Narração densa, corte rápido, legenda animada.",
        "width": 1080,
        "height": 1920,
        "min_seconds": 45,
        "max_seconds": 600,
        "default_seconds": 120,
        "frame_mode": "crop",
    },
    "long": {
        "id": "long",
        "label": "Recap longo 16:9",
        "hint": "Canal de resumo no YouTube. Arco completo, mais trechos e respiro.",
        "width": 1920,
        "height": 1080,
        "min_seconds": 300,
        "max_seconds": 3600,
        "default_seconds": 720,
        "frame_mode": "pad",
    },
}

# Palavras faladas por segundo (PT-BR de narração) — mesma régua do Doutor de Roteiro.
WORDS_PER_SECOND = 2.6

# Teto de blocos por recap e quantos blocos cada chamada de LLM escreve por vez.
# Janelas pequenas = resposta curta, JSON íntegro e nada de timeout em recap longo.
BEATS_HARD_CAP = 420
BEATS_PER_LLM_CALL = 22

# Quantos frames amostrar por minuto de vídeo, com teto para não estourar custo.
FRAMES_PER_MINUTE = 2
MAX_FRAMES = 36
MIN_BEAT_SECONDS = 2.0



class RecapError(RuntimeError):
    """Erro de recap com mensagem pronta para o operador."""


@dataclass
class Shot:
    """Uma cena vista pelo modelo multimodal."""

    at: float
    description: str

    def dict(self) -> dict[str, Any]:
        return {"at": round(self.at, 2), "description": self.description}


@dataclass
class Beat:
    """Um bloco de narração amarrado a um trecho real do vídeo."""

    kind: str  # abertura | corpo | meio | fecho
    text: str
    source_start: float
    # Preenchidos na montagem:
    duration: float = 0.0
    timeline_start: float = 0.0
    audio: Path | None = None
    clip: Path | None = None

    def dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "text": self.text,
            "source_start": round(self.source_start, 2),
            "duration": round(self.duration, 2),
            "timeline_start": round(self.timeline_start, 2),
        }


# --------------------------------------------------------------------------- #
# Presets de blocos fixos (abertura / meio / fecho)
# --------------------------------------------------------------------------- #
def _blocks_file() -> Path:
    config.config_dir.mkdir(parents=True, exist_ok=True)
    return config.config_dir / "recap_blocks.json"


def _load_blocks() -> dict[str, dict[str, Any]]:
    path = _blocks_file()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_blocks(data: dict[str, dict[str, Any]]) -> None:
    _blocks_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return slug[:40] or f"preset_{int(time.time())}"


def list_blocks() -> list[dict[str, Any]]:
    items = list(_load_blocks().values())
    items.sort(key=lambda item: item.get("name", ""))
    return items


def save_block_preset(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise RecapError("Dê um nome ao preset de blocos.")
    preset_id = str(payload.get("id") or "").strip() or slugify(name)
    entry = {
        "id": preset_id,
        "name": name[:60],
        "abertura": str(payload.get("abertura") or "")[:1500],
        "meio": str(payload.get("meio") or "")[:1500],
        "fecho": str(payload.get("fecho") or "")[:1500],
        "updated_at": time.time(),
    }
    data = _load_blocks()
    data[preset_id] = entry
    _save_blocks(data)
    return entry


def delete_block_preset(preset_id: str) -> bool:
    data = _load_blocks()
    if preset_id not in data:
        return False
    data.pop(preset_id)
    _save_blocks(data)
    return True


# --------------------------------------------------------------------------- #
# Camada de IA (texto e visão)
# --------------------------------------------------------------------------- #
_TEXT_ROUTES = [
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat"),
    ("mistral", "https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
]

# Modelos multimodais tentados em ordem — o primeiro que responder vence.
_GEMINI_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest")
_OPENROUTER_VISION = "google/gemini-2.0-flash-001"


def text_ai_available() -> bool:
    return any(api_keys.get_key(pid) for pid, _u, _m in _TEXT_ROUTES)


def vision_available() -> bool:
    return bool(api_keys.get_key("gemini") or api_keys.get_key("openrouter"))


def _extract_json(raw: str) -> dict[str, Any] | None:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _llm_json(system: str, prompt: str, *, job_id: str, timeout: int = 120) -> dict[str, Any]:
    """Chama o primeiro LLM disponível e devolve JSON. Levanta se todos falharem."""
    from .trends import _http_json

    routes = {pid: (url, model) for pid, url, model in _TEXT_ROUTES}
    for provider in api_keys.rank_providers(list(routes)):
        url, model = routes[provider]
        key = api_keys.get_key(provider)
        if not key:
            continue
        try:
            data = _http_json(
                url,
                method="POST",
                headers={"Authorization": f"Bearer {key}"},
                body={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.6,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
            parsed = _extract_json(data["choices"][0]["message"]["content"])
            if parsed:
                jobs.log(job_id, f"Roteirista IA · {provider} · {model}")
                return parsed
        except Exception as exc:  # noqa: BLE001 — provedor fora do ar: tenta o próximo
            jobs.log(job_id, f"Provedor {provider} não respondeu ({exc}). Tentando o próximo.")
            continue
    raise RecapError(
        "Nenhum provedor de IA respondeu. Cadastre em /apis a chave de um LLM "
        "(DeepSeek, Groq, OpenRouter ou Mistral) para gerar o roteiro do recap."
    )


def _vision_gemini(key: str, frames: list[tuple[float, Path]], job_id: str) -> list[Shot]:
    from .trends import _http_json

    parts: list[dict[str, Any]] = [
        {
            "text": (
                "Você é analista de cena de cinema. Para CADA imagem, escreva UMA frase curta em "
                "português do Brasil dizendo o que acontece nela (personagens, ação, lugar, clima). "
                "As imagens estão em ordem cronológica do mesmo vídeo. "
                'Responda SOMENTE JSON: {"cenas":[{"i":0,"d":"descrição"}]}'
            )
        }
    ]
    for _at, path in frames:
        parts.append(
            {
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                }
            }
        )

    for model in _GEMINI_MODELS:
        try:
            data = _http_json(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                method="POST",
                headers={"x-goog-api-key": key},
                body={
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
                timeout=180,
            )
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = _extract_json(text)
            if not parsed:
                continue
            jobs.log(job_id, f"Visão de cena · Gemini · {model}")
            return _shots_from(parsed, frames)
        except Exception:  # noqa: BLE001 — modelo indisponível nessa chave
            continue
    return []


def _vision_openrouter(key: str, frames: list[tuple[float, Path]], job_id: str) -> list[Shot]:
    from .trends import _http_json

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "Para CADA imagem (em ordem cronológica do mesmo vídeo) escreva UMA frase curta em "
                "português do Brasil sobre o que acontece nela. "
                'Responda SOMENTE JSON: {"cenas":[{"i":0,"d":"descrição"}]}'
            ),
        }
    ]
    for _at, path in frames:
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    try:
        data = _http_json(
            "https://openrouter.ai/api/v1/chat/completions",
            method="POST",
            headers={"Authorization": f"Bearer {key}"},
            body={
                "model": _OPENROUTER_VISION,
                "messages": [{"role": "user", "content": content}],
                "response_format": {"type": "json_object"},
            },
            timeout=180,
        )
        parsed = _extract_json(data["choices"][0]["message"]["content"])
        if parsed:
            jobs.log(job_id, f"Visão de cena · OpenRouter · {_OPENROUTER_VISION}")
            return _shots_from(parsed, frames)
    except Exception:  # noqa: BLE001 — segue sem visão
        return []
    return []


def _shots_from(parsed: dict[str, Any], frames: list[tuple[float, Path]]) -> list[Shot]:
    shots: list[Shot] = []
    for item in parsed.get("cenas") or []:
        try:
            index = int(item["i"])
            description = str(item["d"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not description or index < 0 or index >= len(frames):
            continue
        shots.append(Shot(at=frames[index][0], description=description))
    shots.sort(key=lambda s: s.at)
    return shots


def sample_frames(src: Path, duration: float, workdir: Path, job_id: str) -> list[tuple[float, Path]]:
    """Tira fotos do vídeo em intervalos regulares para o modelo multimodal ver."""
    count = max(6, min(MAX_FRAMES, int(duration / 60 * FRAMES_PER_MINUTE) or 6))
    step = duration / (count + 1)
    frames: list[tuple[float, Path]] = []
    workdir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        at = round(step * index, 2)
        dst = workdir / f"frame_{index:03d}.jpg"
        try:
            media.run(
                [
                    config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{at:.2f}", "-i", str(src), "-frames:v", "1",
                    "-vf", "scale=640:-2", "-q:v", "5", str(dst),
                ],
                job_id=None,
            )
        except RuntimeError:
            continue
        if dst.exists() and dst.stat().st_size > 0:
            frames.append((at, dst))
    jobs.log(job_id, f"{len(frames)} frame(s) amostrados para a leitura de cena.")
    return frames


def describe_shots(src: Path, duration: float, workdir: Path, job_id: str) -> list[Shot]:
    """Descreve as cenas do vídeo. Nunca derruba o job: sem visão, devolve []."""
    if not vision_available():
        jobs.log(job_id, "Sem chave Gemini/OpenRouter — seguindo só com a transcrição do áudio.")
        return []
    frames = sample_frames(src, duration, workdir, job_id)
    if not frames:
        return []
    try:
        gemini_key = api_keys.get_key("gemini")
        shots = _vision_gemini(gemini_key, frames, job_id) if gemini_key else []
        if not shots:
            router_key = api_keys.get_key("openrouter")
            shots = _vision_openrouter(router_key, frames, job_id) if router_key else []
        if shots:
            jobs.log(job_id, f"{len(shots)} cena(s) descritas pela leitura visual.")
        else:
            jobs.log(job_id, "A leitura visual não respondeu — seguindo só com o áudio.")
        return shots
    finally:
        for _at, path in frames:
            path.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Roteiro
# --------------------------------------------------------------------------- #
def _timeline_text(segments: list[Segment], shots: list[Shot], duration: float) -> str:
    """Linha do tempo unificada (fala + cena) que o LLM lê para escrever o recap."""
    rows: list[tuple[float, str]] = []
    for seg in segments:
        text = re.sub(r"\s+", " ", seg.text).strip()
        if text:
            rows.append((seg.start, f"FALA {_mmss(seg.start)}: {text}"))
    for shot in shots:
        rows.append((shot.at, f"CENA {_mmss(shot.at)}: {shot.description}"))
    rows.sort(key=lambda row: row[0])

    # Vídeos longos geram milhares de linhas: reduz mantendo a cobertura do arco.
    limit = 420
    if len(rows) > limit:
        step = len(rows) / limit
        rows = [rows[int(i * step)] for i in range(limit)]
    header = f"DURAÇÃO TOTAL: {_mmss(duration)}\n"
    return header + "\n".join(row[1] for row in rows)


def _mmss(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def build_brief(segments: list[Segment], shots: list[Shot], duration: float, job_id: str) -> dict[str, Any]:
    """Descobre nicho, tom, personagens e o arco da história."""
    jobs.stage(job_id, "entendendo", "Lendo a história: nicho, tom e arco narrativo.", progress=35)
    system = (
        "Você é analista de conteúdo audiovisual. Lê uma linha do tempo com falas e descrições de "
        "cena e devolve um diagnóstico honesto da obra. Nunca invente fatos que não aparecem na "
        "linha do tempo. Responda em português do Brasil."
    )
    prompt = (
        "Analise a linha do tempo abaixo e devolve SOMENTE JSON:\n"
        '{"titulo":"como o conteúdo se chama ou do que trata",'
        '"nicho":"terror|drama|acao|comedia|documentario|novela|podcast|noticia|outro",'
        '"tom":"1 a 3 palavras","publico":"quem assiste isso",'
        '"personagens":[{"nome":"","papel":""}],'
        '"atos":[{"ato":"inicio|meio|fim","resumo":"o que acontece","de":"m:ss","ate":"m:ss"}],'
        '"momentos":[{"em":"m:ss","porque":"por que esse instante merece aparecer no recap"}],'
        '"spoiler_final":"o desfecho em 1 frase"}\n\n'
        f"{_timeline_text(segments, shots, duration)}"
    )
    brief = _llm_json(system, prompt, job_id=job_id)
    jobs.log(
        job_id,
        "Diagnóstico: "
        f"{brief.get('titulo') or 'sem título'} · nicho {brief.get('nicho') or '?'} · tom {brief.get('tom') or '?'}",
    )
    return brief


def _parse_ts(value: Any, duration: float) -> float:
    """Aceita '1:23', '01:23:45' ou segundos e devolve segundos dentro do vídeo."""
    if isinstance(value, (int, float)):
        seconds = float(value)
    else:
        text = str(value or "").strip()
        if not text:
            return 0.0
        parts = text.split(":")
        try:
            numbers = [float(p) for p in parts]
        except ValueError:
            return 0.0
        seconds = 0.0
        for number in numbers:
            seconds = seconds * 60 + number
    return max(0.0, min(max(0.0, duration - 0.5), seconds))


def _beats_from_payload(parsed: dict[str, Any], duration: float) -> list[Beat]:
    out: list[Beat] = []
    for item in parsed.get("blocos") or []:
        try:
            text = script_doctor.clean_for_speech(str(item["fala"]).strip())
        except (KeyError, TypeError):
            continue
        if len(text) < 2:
            continue
        out.append(Beat(kind="corpo", text=text, source_start=_parse_ts(item.get("em"), duration)))
    return out


def _slice_window(items, start: float, end: float, key):
    return [item for item in items if start <= key(item) < end]


def write_beats(
    brief: dict[str, Any],
    segments: list[Segment],
    shots: list[Shot],
    *,
    duration: float,
    target_seconds: int,
    style_id: str,
    blocks: dict[str, str],
    job_id: str,
) -> list[Beat]:
    """Escreve o roteiro do recap ancorado em timestamps reais do vídeo.

    Recaps longos são escritos em janelas: cada chamada ao LLM cobre um pedaço
    do vídeo e devolve poucos blocos. Isso evita resposta truncada, JSON
    quebrado e timeout — que é o que fazia narração longa falhar no meio.
    """
    jobs.stage(job_id, "roteirizando", "Escrevendo a narração no tom detectado.", progress=45)
    style = script_doctor.get_style(style_id)
    words_budget = int(target_seconds * WORDS_PER_SECOND)
    # Blocos de ~9 s de narração cada dão ritmo de recap sem virar slideshow.
    beats_target = max(6, min(BEATS_HARD_CAP, int(target_seconds / 9)))
    windows = max(1, -(-beats_target // BEATS_PER_LLM_CALL))

    system = (
        "Você é roteirista de recap narrado em português do Brasil — o formato dos canais de "
        "resumo de filme e série. Escreve para ser FALADO.\n"
        f"ESTILO — {style['label']}:\n{style['briefing']}\n"
        "REGRAS FIXAS:\n"
        "- Cada bloco é uma respiração: 1 a 3 frases curtas.\n"
        "- Nada de markdown, emoji, título ou rubrica entre colchetes.\n"
        "- Não invente fatos, nomes ou números fora da linha do tempo.\n"
        "- O primeiro bloco é gancho: precisa prender nos 3 primeiros segundos.\n"
        "- Cada bloco aponta o instante do vídeo que deve aparecer na tela enquanto ele é narrado."
    )

    beats: list[Beat] = []
    span = duration / windows
    for index in range(windows):
        jobs.check_cancelled(job_id)
        w_start = index * span
        w_end = duration if index == windows - 1 else (index + 1) * span
        w_segments = _slice_window(segments, w_start, w_end, lambda s: s.start) if windows > 1 else segments
        w_shots = _slice_window(shots, w_start, w_end, lambda s: s.at) if windows > 1 else shots
        if windows > 1 and not w_segments and not w_shots:
            continue

        recap_so_far = " ".join(beat.text for beat in beats[-4:])
        prompt = (
            f"DIAGNÓSTICO DA OBRA:\n{json.dumps(brief, ensure_ascii=False)}\n\n"
            + (
                f"PARTE {index + 1} de {windows} — de {_mmss(w_start)} até {_mmss(w_end)}.\n"
                f"ÚLTIMOS BLOCOS JÁ NARRADOS (não repita):\n{recap_so_far or '(nenhum)'}\n\n"
                if windows > 1
                else ""
            )
            + f"LINHA DO TEMPO:\n{_timeline_text(w_segments, w_shots, duration)}\n\n"
            f"Escreva {max(3, beats_target // windows)} blocos, somando cerca de "
            f"{max(60, words_budget // windows)} palavras. "
            + ("Continue a história na ordem, sem recomeçar do zero. " if index else "Cubra o começo da história. ")
            + ("Feche a história no último bloco. " if index == windows - 1 else "")
            + 'Responda SOMENTE JSON: {"blocos":[{"em":"m:ss","fala":"texto narrado"}]}'
        )
        try:
            parsed = _llm_json(system, prompt, job_id=job_id)
        except RecapError:
            if windows == 1 or index == 0:
                raise
            jobs.log(job_id, f"Parte {index + 1}/{windows} do roteiro falhou — seguindo com o resto.")
            continue
        chunk = _beats_from_payload(parsed, duration)
        if windows > 1:
            for beat in chunk:
                if not (w_start <= beat.source_start < w_end):
                    beat.source_start = min(max(beat.source_start, w_start), max(w_start, w_end - 0.5))
        beats.extend(chunk)
        if windows > 1:
            jobs.update(job_id, progress=min(54, 45 + int(9 * (index + 1) / windows)))
            jobs.log(job_id, f"Roteiro parte {index + 1}/{windows} · {len(beats)} bloco(s) até aqui.")

    if not beats:
        raise RecapError("A IA não devolveu nenhum bloco de narração utilizável. Tente de novo.")

    # Mantém a leitura cronológica mesmo se o modelo bagunçar a ordem.
    beats.sort(key=lambda b: b.source_start)
    beats = _insert_fixed_blocks(beats, blocks, duration)
    jobs.log(job_id, f"Roteiro com {len(beats)} bloco(s) de narração.")
    return beats



def _insert_fixed_blocks(beats: list[Beat], blocks: dict[str, str], duration: float) -> list[Beat]:
    """Encaixa abertura, meio e fecho do operador sem quebrar a cronologia."""
    abertura = script_doctor.clean_for_speech((blocks.get("abertura") or "").strip())
    meio = script_doctor.clean_for_speech((blocks.get("meio") or "").strip())
    fecho = script_doctor.clean_for_speech((blocks.get("fecho") or "").strip())

    out: list[Beat] = []
    if abertura:
        out.append(Beat(kind="abertura", text=abertura, source_start=beats[0].source_start))

    if meio:
        middle = len(beats) // 2
        out.extend(beats[:middle])
        anchor = beats[middle].source_start if middle < len(beats) else duration / 2
        out.append(Beat(kind="meio", text=meio, source_start=anchor))
        out.extend(beats[middle:])
    else:
        out.extend(beats)

    if fecho:
        out.append(Beat(kind="fecho", text=fecho, source_start=beats[-1].source_start))
    return out


# --------------------------------------------------------------------------- #
# Montagem
# --------------------------------------------------------------------------- #
def _has_audio(src: Path) -> bool:
    try:
        info = media.probe(src)
    except Exception:  # noqa: BLE001
        return False
    streams = info.get("streams") if isinstance(info, dict) else None
    return any(s.get("codec_type") == "audio" for s in (streams or []))


def _synth(text: str, dst: Path, *, engine: str, voice: str, rate: int, job_id: str) -> Path:
    if engine == "elevenlabs":
        voice_engine.text_to_speech(text, dst, voice_id=voice, job_id=job_id)
    else:
        edge_tts.synthesize(text, dst, voice=voice, job_id=job_id, rate_percent=rate)
    return dst


def _apply_persona(src: Path, dst: Path, persona) -> Path:
    chain = voice_forge.filter_chain(persona, preserve_duration=True)
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src), "-filter:a", ",".join(chain),
            "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(dst),
        ],
        job_id=None,
    )
    src.unlink(missing_ok=True)
    return dst


def _frame_filter(width: int, height: int, mode: str) -> str:
    if mode == "pad":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30"
        )
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps=30"
    )


def _render_beat(
    src: Path,
    beat: Beat,
    dst: Path,
    *,
    width: int,
    height: int,
    frame_mode: str,
    ambience: float,
    source_has_audio: bool,
    source_duration: float,
    job_id: str,
) -> Path:
    """Recorta o trecho do vídeo exatamente na duração da narração e mixa o áudio."""
    duration = beat.duration
    start = max(0.0, min(beat.source_start, max(0.0, source_duration - 0.5)))

    cmd = [
        config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-i", str(src),
        "-i", str(beat.audio),
    ]
    video_chain = (
        f"[0:v]{_frame_filter(width, height, frame_mode)},"
        f"tpad=stop_mode=clone:stop_duration={duration + 1:.3f},trim=duration={duration:.3f},setpts=PTS-STARTPTS[v]"
    )
    if source_has_audio and ambience > 0:
        audio_chain = (
            f"[0:a]aresample={SAMPLE_RATE},volume={ambience:.2f},highpass=f=140,"
            f"apad=whole_dur={duration + 1:.3f},atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[bg];"
            f"[1:a]aresample={SAMPLE_RATE},volume=1.0[vo];"
            "[bg][vo]amix=inputs=2:duration=first:dropout_transition=0,"
            f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:channel_layouts=stereo[a]"
        )
    else:
        audio_chain = (
            f"[1:a]aresample={SAMPLE_RATE},"
            f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:channel_layouts=stereo[a]"
        )

    cmd += [
        "-filter_complex", f"{video_chain};{audio_chain}",
        "-map", "[v]", "-map", "[a]",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE), "-ac", "2",
        "-video_track_timescale", "30000",
        str(dst),
    ]
    media.run(cmd, job_id=None)
    if not dst.exists() or dst.stat().st_size == 0:
        raise RecapError(f"Falha ao montar o bloco de narração em {_mmss(start)}.")
    return dst


def _concat(parts: list[Path], dst: Path, job_id: str) -> Path:
    listing = dst.parent / f"{dst.stem}_concat.txt"
    listing.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts), encoding="utf-8")
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-c", "copy", str(dst),
        ],
        job_id=job_id,
    )
    listing.unlink(missing_ok=True)
    return dst


def narrate_and_assemble(
    src: Path,
    beats: list[Beat],
    dst: Path,
    *,
    workdir: Path,
    width: int,
    height: int,
    frame_mode: str,
    ambience: float,
    engine: str,
    voice: str,
    rate: int,
    persona,
    source_duration: float,
    job_id: str,
) -> list[Beat]:
    """Narra cada bloco, monta o clipe correspondente e cola tudo em `dst`."""
    jobs.stage(job_id, "narrando", "Gerando a narração e montando os trechos.", progress=55)
    workdir.mkdir(parents=True, exist_ok=True)
    source_has_audio = _has_audio(src)
    clips: list[Path] = []
    cursor = 0.0

    for index, beat in enumerate(beats, start=1):
        jobs.check_cancelled(job_id)
        raw = workdir / f"nar_{index:03d}_raw.wav"
        final_audio = workdir / f"nar_{index:03d}.wav"
        _synth(beat.text, raw, engine=engine, voice=voice, rate=rate, job_id=job_id)
        if persona is not None and engine != "elevenlabs":
            beat.audio = _apply_persona(raw, final_audio, persona)
        else:
            raw.replace(final_audio)
            beat.audio = final_audio

        beat.duration = max(MIN_BEAT_SECONDS, media.probe_duration(beat.audio))
        beat.timeline_start = cursor
        cursor += beat.duration

        clip = workdir / f"clip_{index:03d}.mp4"
        _render_beat(
            src,
            beat,
            clip,
            width=width,
            height=height,
            frame_mode=frame_mode,
            ambience=ambience,
            source_has_audio=source_has_audio,
            source_duration=source_duration,
            job_id=job_id,
        )
        beat.clip = clip
        clips.append(clip)
        beat.audio.unlink(missing_ok=True)

        jobs.update(job_id, progress=min(82, 55 + int(27 * index / len(beats))))
        if index % 3 == 0 or index == len(beats):
            jobs.log(job_id, f"Recap {index}/{len(beats)} blocos narrados e montados.")

    jobs.stage(job_id, "montando", "Colando os trechos na ordem da história.", progress=85)
    _concat(clips, dst, job_id)
    for clip in clips:
        clip.unlink(missing_ok=True)
    return beats


def caption_lines(beats: list[Beat], *, max_words: int = 4):
    """Converte os blocos narrados em linhas de legenda na régua da timeline."""
    from . import captions

    pseudo = [
        Segment(start=beat.timeline_start, end=beat.timeline_start + beat.duration, text=beat.text)
        for beat in beats
        if beat.text
    ]
    return captions.lines_from_segments(pseudo, max_words=max_words)


def sweep(*paths: Path | None) -> None:
    """Remove intermediários sem nunca derrubar o job."""
    for path in paths:
        if not path:
            continue
        try:
            if path.is_dir():
                for child in sorted(path.rglob("*"), reverse=True):
                    try:
                        child.unlink() if child.is_file() else child.rmdir()
                    except OSError:
                        continue
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def catalog() -> dict[str, Any]:
    from . import captions

    return {
        "formats": list(FORMATS.values()),
        "styles": script_doctor.list_styles(),
        "personas": voice_forge.list_personas(),
        "caption_presets": captions.preset_catalog(),
        "blocks": list_blocks(),
        "words_per_second": WORDS_PER_SECOND,
        "ai_ready": text_ai_available(),
        "vision_ready": vision_available(),
        "forge_ready": edge_tts.available(),
        "elevenlabs_ready": bool(api_keys.get_key("elevenlabs")),
    }
