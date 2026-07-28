"""Detecção inteligente de melhores momentos (motor da Fábrica de Cortes).

Entrada: os segmentos transcritos do vídeo longo (`transcribe.Segment`).
Saída: janelas de tempo prontas para virar corte vertical, cada uma com título,
nota e motivo — sempre respeitando a faixa de duração que o operador escolheu.

Como pontua
-----------
1. **Camada determinística (sempre roda, sem chave de API)** — gancho de
   abertura, palavras de alta retenção do nicho, densidade de fala, números e
   dados concretos, carga emocional, fechamento de frase e "payoff" no fim.
2. **Camada de IA (opcional)** — se houver chave de LLM na Central de APIs, os
   melhores candidatos são reordenados e ganham título/motivo escritos por um
   editor especialista no nicho. Sem chave, a camada 1 já entrega cortes bons.

O operador nunca escolhe quantidade: o motor devolve quantos cortes o vídeo
realmente aguenta dentro do intervalo de tempo pedido.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from . import api_keys

MAX_CLIPS_HARD = 24
MIN_WINDOW = 8.0
MAX_WINDOW = 1800.0

# Ordem de preferência de LLM: gratuito → barato → reserva (igual ao storyboard).
_ROUTES = [
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat"),
    ("mistral", "https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
    ("siliconflow", "https://api.siliconflow.com/v1/chat/completions", "deepseek-ai/DeepSeek-V3"),
]

# Gatilhos universais de retenção (valem para qualquer nicho).
HOOK_OPENERS = (
    "o que", "por que", "porque", "voce sabia", "ninguem", "nunca", "sempre",
    "a verdade", "o segredo", "atencao", "olha isso", "imagina", "existe",
    "se voce", "quando eu", "eu descobri", "presta atencao", "para tudo",
    "a maioria", "todo mundo", "escuta", "veja bem", "vou te contar",
)
EMOTION_WORDS = (
    "incrivel", "absurdo", "chocante", "brutal", "impressionante", "perigoso",
    "erro", "fracasso", "sucesso", "medo", "coragem", "amor", "odio", "dor",
    "mudou", "mudanca", "chorei", "revoltante", "inacreditavel", "surreal",
    "louco", "insano", "historia", "verdade", "mentira", "segredo",
)
PAYOFF_WORDS = (
    "por isso", "resultado", "conclusao", "no fim", "resumindo", "ou seja",
    "moral da historia", "entao", "portanto", "e foi assim",
)
FILLER_WORDS = ("eh", "ahn", "tipo assim", "ne", "sabe", "hum")

NICHES: list[dict[str, Any]] = [
    {
        "id": "auto",
        "label": "Detectar sozinho (universal)",
        "emoji": "🎯",
        "resumo": "Sem viés de tema: usa só gancho, emoção, densidade e payoff.",
        "keywords": [],
        "briefing": "Corte genérico de alta retenção, sem viés de nicho.",
    },
    {
        "id": "motivacao",
        "label": "Motivação / Mentalidade",
        "emoji": "🔥",
        "resumo": "Viradas de chave, disciplina, superação e frases de impacto.",
        "keywords": [
            "disciplina", "foco", "habito", "mentalidade", "desistir", "levantar",
            "sacrificio", "rotina", "proposito", "fracasso", "vencer", "esforco",
            "acordar", "consistencia", "desculpa", "responsabilidade", "sofrer",
        ],
        "briefing": "Cortes de motivação: cada corte precisa terminar numa frase de impacto.",
    },
    {
        "id": "negocios",
        "label": "Negócios / Dinheiro",
        "emoji": "💰",
        "resumo": "Números, faturamento, erro caro, estratégia e bastidor.",
        "keywords": [
            "dinheiro", "faturamento", "lucro", "empresa", "cliente", "venda",
            "investir", "mercado", "negocio", "caixa", "prejuizo", "salario",
            "milhao", "reais", "dolar", "imposto", "socio", "escala", "margem",
        ],
        "briefing": "Cortes de negócios: prioriza número concreto, erro caro e tática aplicável.",
    },
    {
        "id": "podcast",
        "label": "Podcast / Entrevista",
        "emoji": "🎙️",
        "resumo": "Histórias fechadas, respostas polêmicas e reações.",
        "keywords": [
            "pergunta", "resposta", "conta", "aconteceu", "historia", "cara",
            "olha", "na epoca", "eu vi", "me falaram", "polemica", "opiniao",
        ],
        "briefing": "Cortes de podcast: a história tem que começar e terminar dentro do corte.",
    },
    {
        "id": "educacao",
        "label": "Educação / Tutorial",
        "emoji": "📚",
        "resumo": "Explicações completas, passo a passo e conceitos fechados.",
        "keywords": [
            "primeiro", "segundo", "passo", "exemplo", "funciona", "conceito",
            "significa", "aprender", "estudar", "prova", "regra", "formula",
            "tecnica", "metodo", "erro comum", "dica",
        ],
        "briefing": "Cortes didáticos: o conceito precisa estar completo e útil sozinho.",
    },
    {
        "id": "saude",
        "label": "Saúde / Fitness",
        "emoji": "💪",
        "resumo": "Treino, dieta, mito x verdade e alerta de saúde.",
        "keywords": [
            "treino", "musculo", "dieta", "proteina", "caloria", "gordura",
            "emagrecer", "hipertrofia", "sono", "hormonio", "lesao", "saude",
            "medico", "exame", "remedio", "suplemento", "jejum",
        ],
        "briefing": "Cortes de saúde: prioriza mito derrubado, alerta e protocolo prático.",
    },
    {
        "id": "tecnologia",
        "label": "Tecnologia / IA",
        "emoji": "🤖",
        "resumo": "Novidade, comparação, previsão e demonstração.",
        "keywords": [
            "inteligencia artificial", "modelo", "algoritmo", "software", "app",
            "dados", "codigo", "automacao", "robo", "chip", "internet", "prompt",
            "tecnologia", "futuro", "startup", "programar",
        ],
        "briefing": "Cortes de tecnologia: prioriza novidade concreta e implicação prática.",
    },
    {
        "id": "religiao",
        "label": "Fé / Espiritualidade",
        "emoji": "🙏",
        "resumo": "Testemunho, versículo, virada e consolo.",
        "keywords": [
            "deus", "fe", "oracao", "biblia", "senhor", "espirito", "milagre",
            "testemunho", "igreja", "proposito", "perdao", "gratidao", "benção",
        ],
        "briefing": "Cortes de fé: prioriza testemunho fechado e frase de consolo forte.",
    },
    {
        "id": "true_crime",
        "label": "True Crime / Mistério",
        "emoji": "🕵️",
        "resumo": "Caso, reviravolta, prova e desfecho.",
        "keywords": [
            "crime", "policia", "caso", "vitima", "suspeito", "corpo", "prova",
            "investigacao", "desaparecid", "assassin", "julgamento", "delegado",
            "misterio", "camera", "testemunha",
        ],
        "briefing": "Cortes de true crime: o corte precisa ter tensão no começo e revelação no fim.",
    },
    {
        "id": "comedia",
        "label": "Comédia / Reação",
        "emoji": "😂",
        "resumo": "Punchline, absurdo e resposta afiada.",
        "keywords": [
            "kkk", "risada", "piada", "zoeira", "vergonha", "mico", "absurdo",
            "cara", "mano", "gente", "surreal", "papelao",
        ],
        "briefing": "Cortes de comédia: o corte termina na punchline, nunca depois dela.",
    },
    {
        "id": "esporte",
        "label": "Esporte",
        "emoji": "⚽",
        "resumo": "Lance, opinião polêmica e bastidor.",
        "keywords": [
            "jogo", "time", "gol", "tecnico", "jogador", "campeonato", "titulo",
            "torcida", "contrato", "treino", "final", "arbitro", "lance",
        ],
        "briefing": "Cortes de esporte: prioriza opinião polêmica e bastidor inédito.",
    },
]

NICHE_IDS = {n["id"] for n in NICHES}


def catalog() -> list[dict[str, Any]]:
    return [
        {k: n[k] for k in ("id", "label", "emoji", "resumo")}
        for n in NICHES
    ]


def get_niche(niche_id: str) -> dict[str, Any]:
    for niche in NICHES:
        if niche["id"] == niche_id:
            return niche
    return NICHES[0]


def llm_available() -> bool:
    return any(api_keys.get_key(pid) for pid, _u, _m in _ROUTES)


# --------------------------------------------------------------------------- #
# Normalização
# --------------------------------------------------------------------------- #
def _fold(text: str) -> str:
    """Minúsculas sem acento — comparação estável em qualquer idioma latino."""
    norm = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


def _units(segments: list[Any]) -> list[dict[str, Any]]:
    """Segmento do Whisper vira unidade de corte com texto limpo."""
    units: list[dict[str, Any]] = []
    for seg in segments:
        text = str(getattr(seg, "text", "") or "").strip()
        start = float(getattr(seg, "start", 0.0) or 0.0)
        end = float(getattr(seg, "end", 0.0) or 0.0)
        if not text or end <= start:
            continue
        units.append({"start": start, "end": end, "text": text, "flat": _fold(text)})
    units.sort(key=lambda u: u["start"])
    return units


# --------------------------------------------------------------------------- #
# Pontuação determinística
# --------------------------------------------------------------------------- #
def _score(window: list[dict[str, Any]], niche: dict[str, Any], previous: dict | None) -> tuple[float, list[str]]:
    text = " ".join(u["text"] for u in window).strip()
    flat = _fold(text)
    words = [w for w in flat.split() if w]
    seconds = max(0.5, window[-1]["end"] - window[0]["start"])
    reasons: list[str] = []
    score = 1.0

    # 1. Gancho de abertura — vale muito nos 3 primeiros segundos.
    head = " ".join(flat.split()[:14])
    if any(head.startswith(op) or f" {op}" in head for op in HOOK_OPENERS):
        score += 2.4
        reasons.append("abre com gancho")
    if head.rstrip().endswith("?") or "?" in " ".join(text.split()[:14]):
        score += 1.1
        reasons.append("abre com pergunta")

    # 2. Palavras do nicho.
    hits = sum(1 for kw in niche["keywords"] if kw in flat)
    if hits:
        score += min(3.0, hits * 0.55)
        reasons.append(f"{hits} termo(s) do nicho")

    # 3. Carga emocional.
    emotion = sum(1 for kw in EMOTION_WORDS if kw in flat)
    if emotion:
        score += min(2.0, emotion * 0.35)
        reasons.append("carga emocional alta")

    # 4. Dado concreto (número/percentual/valor).
    numbers = len(re.findall(r"\b\d[\d.,]*\b|\b(mil|milh|bilh|por cento|%)", flat))
    if numbers:
        score += min(1.6, numbers * 0.3)
        reasons.append("tem número/dado")

    # 5. Densidade de fala — silêncio comprido derruba retenção.
    density = len(words) / seconds
    if density >= 2.2:
        score += 1.0
        reasons.append("fala densa")
    elif density < 1.1:
        score -= 1.4
        reasons.append("muita pausa")

    # 6. Payoff no fim.
    tail = " ".join(flat.split()[-18:])
    if any(kw in tail for kw in PAYOFF_WORDS):
        score += 1.2
        reasons.append("fecha com conclusão")
    if text.rstrip().endswith((".", "!", "?", "…")):
        score += 0.7
    else:
        score -= 0.9
        reasons.append("frase cortada no fim")

    # 7. Começo limpo — não entrar no meio de uma frase.
    if previous is not None and not previous["text"].rstrip().endswith((".", "!", "?", "…")):
        score -= 0.8

    # 8. Muleta de fala derruba um pouco.
    fillers = sum(flat.count(f" {f} ") for f in FILLER_WORDS)
    if fillers > 6:
        score -= 0.6

    return round(score, 3), reasons[:4]


def _title(text: str) -> str:
    first = re.split(r"(?<=[.!?…])\s+", text.strip())[0]
    words = first.split()
    title = " ".join(words[:9])
    return (title[:78] + "…") if len(title) > 78 else title


# --------------------------------------------------------------------------- #
# Busca das janelas
# --------------------------------------------------------------------------- #
def find(
    segments: list[Any],
    *,
    niche_id: str = "auto",
    min_seconds: float = 60.0,
    max_seconds: float = 180.0,
    max_clips: int = 0,
    total_duration: float = 0.0,
) -> list[dict[str, Any]]:
    """Devolve cortes não sobrepostos, do melhor para o pior."""
    niche = get_niche(niche_id)
    low = max(MIN_WINDOW, float(min_seconds))
    high = max(low + 2.0, min(MAX_WINDOW, float(max_seconds)))

    units = _units(segments)
    if not units:
        return []

    candidates: list[dict[str, Any]] = []
    for i, unit in enumerate(units):
        best: dict[str, Any] | None = None
        window: list[dict[str, Any]] = []
        for j in range(i, len(units)):
            window.append(units[j])
            span = units[j]["end"] - unit["start"]
            if span < low:
                continue
            if span > high:
                break
            score, reasons = _score(window, niche, units[i - 1] if i else None)
            # Cortes muito curtos dentro da faixa ganham um empurrão leve:
            # entregam mais cortes bons por vídeo.
            score += max(0.0, (high - span) / max(1.0, high)) * 0.35
            if best is None or score > best["score"]:
                text = " ".join(u["text"] for u in window).strip()
                best = {
                    "start": round(max(0.0, unit["start"] - 0.25), 2),
                    "end": round(units[j]["end"] + 0.35, 2),
                    "seconds": round(span, 2),
                    "score": round(score, 3),
                    "reasons": reasons,
                    "text": text,
                    "title": _title(text),
                }
        if best:
            candidates.append(best)

    if not candidates:
        return []

    if total_duration > 0:
        for cand in candidates:
            cand["end"] = round(min(cand["end"], total_duration), 2)
            cand["seconds"] = round(cand["end"] - cand["start"], 2)

    candidates.sort(key=lambda c: c["score"], reverse=True)

    limit = int(max_clips or 0)
    if limit <= 0:
        # Quantidade automática: ~1 corte a cada 4 janelas de duração máxima,
        # sempre limitado pelo que o vídeo realmente aguenta.
        span = total_duration or (units[-1]["end"] - units[0]["start"])
        limit = max(1, min(MAX_CLIPS_HARD, int(span // max(high, 1.0)) + 2))
    limit = max(1, min(MAX_CLIPS_HARD, limit))

    chosen: list[dict[str, Any]] = []
    for cand in candidates:
        if len(chosen) >= limit:
            break
        if any(cand["start"] < c["end"] + 0.8 and c["start"] < cand["end"] + 0.8 for c in chosen):
            continue
        if cand["score"] < 0.6 and chosen:
            continue
        chosen.append(cand)

    chosen.sort(key=lambda c: c["start"])
    for index, clip in enumerate(chosen):
        clip["index"] = index
    return chosen


# --------------------------------------------------------------------------- #
# Camada de IA — reordena e batiza os cortes
# --------------------------------------------------------------------------- #
def refine(
    clips: list[dict[str, Any]],
    *,
    niche_id: str = "auto",
    language: str = "português do Brasil",
    timeout: int = 60,
) -> dict[str, Any]:
    """Pede ao LLM títulos, notas e motivos. Falhou? Mantém a heurística."""
    if not clips:
        return {"clips": clips, "provider": None}

    from .trends import _http_json  # cliente HTTP com timeout já usado no projeto

    niche = get_niche(niche_id)
    payload = [
        {"id": c["index"], "segundos": c["seconds"], "texto": c["text"][:900]}
        for c in clips
    ]
    system = (
        "Você é editor sênior de cortes virais (TikTok/Reels/Shorts).\n"
        f"NICHO: {niche['label']} — {niche['briefing']}\n"
        f"IDIOMA DAS RESPOSTAS: {language}.\n"
        "Receberá trechos JÁ recortados de um vídeo longo. Para CADA trecho devolva:\n"
        "- `nota` de 0 a 10 (potencial real de retenção nos 3 primeiros segundos + payoff);\n"
        "- `titulo` de até 60 caracteres, estilo capa de corte, sem hashtag e sem emoji;\n"
        "- `motivo` de até 90 caracteres explicando por que funciona ou por que é fraco.\n"
        "Nunca invente informação que não está no trecho.\n"
        'Responda SOMENTE JSON: {"cortes":[{"id":0,"nota":0,"titulo":"...","motivo":"..."}]}'
    )

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
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                    "temperature": 0.4,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
            content = data["choices"][0]["message"]["content"]
            start, end = content.find("{"), content.rfind("}")
            if start == -1 or end == -1:
                continue
            parsed = json.loads(content[start : end + 1])
            rows = parsed.get("cortes") or parsed.get("clips") or []
            by_id = {c["index"]: c for c in clips}
            touched = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                clip = by_id.get(int(row.get("id", -1)))
                if clip is None:
                    continue
                title = str(row.get("titulo") or "").strip()[:80]
                motive = str(row.get("motivo") or "").strip()[:120]
                try:
                    rating = float(row.get("nota") or 0)
                except (TypeError, ValueError):
                    rating = 0.0
                if title:
                    clip["title"] = title
                if motive:
                    clip["reasons"] = [motive]
                if rating > 0:
                    clip["ai_score"] = round(min(10.0, rating), 1)
                touched += 1
            if touched:
                return {"clips": clips, "provider": provider, "model": model}
        except Exception:  # noqa: BLE001 — provedor fora do ar: tenta o próximo
            continue

    return {"clips": clips, "provider": None}
