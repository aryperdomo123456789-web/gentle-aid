"""Storyboard por IA — transforma um prompt em cenas prontas para montagem.

O gerador de vídeo (estilo "canal de IA": narração + imagens + legenda animada)
começa aqui. Este serviço NÃO desenha nada e NÃO chama FFmpeg: ele só quebra a
ideia do usuário em cenas com narração, descrição visual e duração estimada.

Roteamento de LLM
-----------------
Groq primeiro (gratuito e rápido), DeepSeek como reserva, depois OpenRouter e
Mistral. As chaves vêm sempre da Central de APIs (`api_keys`), nunca de
`os.environ` direto. Sem nenhuma chave, cai num storyboard determinístico feito
a partir do próprio texto — o usuário continua conseguindo gerar vídeo.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import api_keys
from .script_doctor import STYLES, clean_for_speech, get_style

WORDS_PER_SECOND = 2.6
MIN_SCENES = 3
MAX_SCENES = 24

# Ordem de preferência: gratuito → barato → reserva.
_ROUTES = [
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat"),
    ("mistral", "https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
    ("siliconflow", "https://api.siliconflow.com/v1/chat/completions", "deepseek-ai/DeepSeek-V3"),
]

# Direções de arte — viram sufixo do prompt de imagem, mantendo o vídeo coerente.
LOOKS: list[dict[str, str]] = [
    {
        "id": "cartoon",
        "label": "Cartoon 3D (estilo canal viral)",
        "suffix": (
            "3d cartoon illustration, pixar-like render, bold shapes, saturated colors, "
            "soft studio lighting, clean background, vertical composition"
        ),
    },
    {
        "id": "cinema",
        "label": "Cinematográfico realista",
        "suffix": (
            "cinematic photography, 35mm, shallow depth of field, dramatic natural light, "
            "high detail, color graded, vertical composition"
        ),
    },
    {
        "id": "noir",
        "label": "Sombrio / Terror",
        "suffix": (
            "dark moody scene, low key lighting, fog, deep shadows, desaturated palette, "
            "grain, unsettling atmosphere, vertical composition"
        ),
    },
    {
        "id": "news",
        "label": "Notícia / Documental",
        "suffix": (
            "documentary photo, photojournalism, realistic, neutral colors, natural light, "
            "editorial framing, vertical composition"
        ),
    },
    {
        "id": "retro",
        "label": "Retrô / Anos 90",
        "suffix": (
            "retro 90s aesthetic, vhs grain, warm film colors, analog photography, "
            "nostalgic mood, vertical composition"
        ),
    },
    {
        "id": "anime",
        "label": "Anime",
        "suffix": (
            "anime key visual, cel shaded, expressive characters, vivid colors, "
            "dynamic composition, studio quality, vertical composition"
        ),
    },
]

LOOK_IDS = {look["id"] for look in LOOKS}


def look(look_id: str) -> dict[str, str]:
    for item in LOOKS:
        if item["id"] == look_id:
            return item
    return LOOKS[0]


def styles() -> list[dict[str, Any]]:
    """Reaproveita o catálogo narrativo do Doutor de Roteiro."""
    return [
        {k: s[k] for k in ("id", "label", "emoji", "resumo", "ritmo") if k in s}
        for s in STYLES
    ]


def llm_available() -> bool:
    return any(api_keys.get_key(pid) for pid, _u, _m in _ROUTES)


def _system_prompt(style: dict[str, Any], scenes: int, seconds: int, language: str) -> str:
    per_scene = max(2.5, round(seconds / max(1, scenes), 1))
    return (
        "Você é roteirista e diretor de vídeos curtos virais (TikTok/Reels/Shorts).\n"
        f"IDIOMA DA NARRAÇÃO: {language}.\n"
        f"ESTILO — {style['label']}:\n{style['briefing']}\n"
        "TAREFA: transformar a ideia do usuário num storyboard pronto para montagem "
        "automática (narração + imagem por cena + legenda queimada).\n"
        "REGRAS:\n"
        f"- Exatamente {scenes} cenas, cerca de {per_scene}s cada (total ~{seconds}s).\n"
        "- `narracao`: texto FALADO, sem markdown, sem emoji, sem rubrica, números por extenso, "
        "nenhuma frase com mais de 22 palavras.\n"
        "- A cena 1 é o gancho: no máximo 12 palavras e uma tensão/promessa clara.\n"
        "- `visual`: descrição da IMAGEM da cena em INGLÊS, concreta e visualizável "
        "(sujeito + ação + ambiente + enquadramento). Nunca escreva texto dentro da imagem.\n"
        "- `busca`: 2 a 4 palavras em inglês para buscar b-roll em banco de vídeos.\n"
        "- Mantenha o MESMO personagem/ambiente entre as cenas quando fizer sentido.\n"
        "- Não invente dados, nomes ou números que o usuário não deu.\n"
        'Responda SOMENTE JSON válido: {"titulo":"...","gancho":"...","cta":"...",'
        '"cenas":[{"narracao":"...","visual":"...","busca":"...","segundos":0}]}'
    )


def _fallback(prompt: str, scenes: int, seconds: int) -> list[dict[str, Any]]:
    """Sem chave de IA: quebra o próprio texto do usuário em cenas."""
    text = clean_for_speech(prompt)
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+|\n+", text) if p.strip()]
    if not parts:
        parts = [prompt.strip() or "Cena inicial."]
    while len(parts) < scenes:
        parts.append(parts[len(parts) % len(parts)])
    chunk = max(1, len(parts) // scenes)
    grouped = [" ".join(parts[i : i + chunk]) for i in range(0, len(parts), chunk)][:scenes]
    per = round(seconds / max(1, len(grouped)), 1)
    return [
        {
            "index": i,
            "narration": narration,
            "visual": narration[:180],
            "query": " ".join(narration.split()[:4]),
            "seconds": per,
        }
        for i, narration in enumerate(grouped)
    ]


def _normalize_scene(raw: Any, index: int, fallback_seconds: float) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    narration = clean_for_speech(str(raw.get("narracao") or raw.get("narration") or "").strip())
    if not narration:
        return None
    try:
        seconds = float(raw.get("segundos") or raw.get("seconds") or 0)
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds <= 0:
        seconds = max(2.0, len(narration.split()) / WORDS_PER_SECOND)
    return {
        "index": index,
        "narration": narration,
        "visual": str(raw.get("visual") or narration)[:400].strip(),
        "query": str(raw.get("busca") or raw.get("query") or "").strip()[:80],
        "seconds": round(min(30.0, max(1.5, seconds or fallback_seconds)), 1),
    }


def plan(
    prompt: str,
    *,
    style_id: str = "neutro",
    scenes: int = 8,
    seconds: int = 45,
    language: str = "português do Brasil",
    instruction: str = "",
    timeout: int = 90,
) -> dict[str, Any]:
    """Devolve `{title, hook, cta, scenes[], provider, fallback}`."""
    from .trends import _http_json  # cliente HTTP com timeout/retry já usado no projeto

    style = get_style(style_id)
    scenes = max(MIN_SCENES, min(MAX_SCENES, int(scenes or 8)))
    seconds = max(10, min(600, int(seconds or 45)))
    user = f"IDEIA DO USUÁRIO:\n\"\"\"\n{prompt.strip()}\n\"\"\""
    if instruction.strip():
        user += f"\n\nPedido extra: {instruction.strip()}"

    routes = {pid: (url, model) for pid, url, model in _ROUTES}
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
                        {"role": "system", "content": _system_prompt(style, scenes, seconds, language)},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.8,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
            content = data["choices"][0]["message"]["content"]
            start, end = content.find("{"), content.rfind("}")
            if start == -1 or end == -1:
                continue
            parsed = json.loads(content[start : end + 1])
            raw_scenes = parsed.get("cenas") or parsed.get("scenes") or []
            per = seconds / max(1, len(raw_scenes) or scenes)
            built: list[dict[str, Any]] = []
            for raw in raw_scenes:
                scene = _normalize_scene(raw, len(built), per)
                if scene:
                    built.append(scene)
                if len(built) >= MAX_SCENES:
                    break
            if len(built) < MIN_SCENES:
                continue
            return {
                "title": str(parsed.get("titulo") or "").strip()[:140] or prompt.strip()[:140],
                "hook": str(parsed.get("gancho") or "").strip()[:200],
                "cta": str(parsed.get("cta") or "").strip()[:200],
                "scenes": built,
                "style": style["id"],
                "provider": provider,
                "model": model,
                "fallback": False,
                "total_seconds": round(sum(s["seconds"] for s in built), 1),
            }
        except Exception:  # noqa: BLE001 — provedor fora do ar: tenta o próximo
            continue

    built = _fallback(prompt, scenes, seconds)
    return {
        "title": prompt.strip()[:140] or "Roteiro sem título",
        "hook": built[0]["narration"][:200] if built else "",
        "cta": "",
        "scenes": built,
        "style": style["id"],
        "provider": None,
        "model": None,
        "fallback": True,
        "total_seconds": round(sum(s["seconds"] for s in built), 1),
        "note": (
            "Nenhum provedor de IA respondeu. Cadastre Groq (grátis) ou DeepSeek em /apis "
            "para o storyboard sair no estilo escolhido."
        ),
    }
