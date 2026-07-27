"""Doutor de Roteiro — corrige e reescreve o texto ANTES de virar áudio.

Por que existe
--------------
A voz só é tão boa quanto o roteiro. Texto de blog, legenda copiada do TikTok ou
transcrição bruta soam péssimos narrados: frases longas demais, números escritos
em algarismo, siglas grudadas, zero gancho nos 3 primeiros segundos.

Este serviço faz duas coisas:

1. **Correção determinística (sempre roda, sem chave de API)** — normaliza
   pontuação, quebra parágrafos gigantes, tira muletas, marca respiração e
   aponta problemas concretos (`diagnostics`). É o mesmo tipo de checagem do
   laboratório de legendas: regra pura, testável, sem depender de rede.
2. **Reescrita por IA no estilo escolhido** — envia o texto para o LLM já
   configurado na Central de APIs (DeepSeek/Groq/OpenRouter/Mistral) com um
   briefing específico do estilo narrativo (terror, notícia, true crime…).
   Sem chave, o passo 1 sozinho já devolve um roteiro melhor.

Os estilos foram montados a partir dos formatos que mais retêm em vídeo curto
(narração de terror/creepypasta, plantão de notícia, true crime, documentário,
storytime, oferta direta, curiosidades em lista, ASMR, motivacional, esporte,
conspiração e comédia/roast).
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import api_keys

# --------------------------------------------------------------------------- #
# Catálogo de estilos narrativos
# --------------------------------------------------------------------------- #
# briefing = instrução enviada ao LLM. rules  = o que a IA NÃO pode fazer.
STYLES: list[dict[str, Any]] = [
    {
        "id": "terror",
        "label": "Terror / Creepypasta",
        "emoji": "🕯️",
        "resumo": "Relato sombrio em primeira pessoa, tensão crescente e final que gela.",
        "ritmo": "lento",
        "briefing": (
            "Narração de terror em primeira pessoa, como um relato real que a pessoa nunca contou "
            "para ninguém. Abre com uma frase curta e perturbadora. Usa presente do indicativo nos "
            "momentos de tensão. Detalhe sensorial (som, cheiro, temperatura) em vez de adjetivo "
            "vazio. A cada 3 ou 4 frases, uma frase de 3 a 5 palavras para dar respiro. Termina com "
            "uma revelação curta, sem explicar demais."
        ),
        "expressividade": 0.45,
        "velocidade": "0.9",
    },
    {
        "id": "noticia",
        "label": "Notícia / Plantão urgente",
        "emoji": "📰",
        "resumo": "Lead jornalístico: o fato primeiro, depois o contexto.",
        "ritmo": "rápido",
        "briefing": (
            "Locução de plantão jornalístico. Primeira frase é o lead: o que aconteceu, com quem, "
            "onde e quando. Frases afirmativas, voz ativa, sem adjetivo opinativo. Cada parágrafo "
            "entrega um fato novo. Números por extenso quando falados. Encerra com o desdobramento "
            "('o que acontece agora'). Nunca inventa dado, fonte, nome ou data que não esteja no "
            "texto original."
        ),
        "expressividade": 0.15,
        "velocidade": "1.1",
    },
    {
        "id": "true_crime",
        "label": "True Crime / Caso real",
        "emoji": "🔎",
        "resumo": "Investigação em capítulos, com pistas soltas e virada no fim.",
        "ritmo": "médio",
        "briefing": (
            "Narração de caso real no estilo true crime. Abre pelo detalhe mais estranho do caso, "
            "não pelo começo cronológico. Constrói em pequenos capítulos: cena, personagem, pista, "
            "contradição, virada. Tom sóbrio, sem sensacionalismo barato. Faz perguntas retóricas "
            "curtas para segurar o espectador. Preserva rigorosamente os fatos do texto original."
        ),
        "expressividade": 0.3,
        "velocidade": "1",
    },
    {
        "id": "documentario",
        "label": "Documentário",
        "emoji": "🎬",
        "resumo": "Voz de documentário: autoridade calma, imagem mental forte.",
        "ritmo": "lento",
        "briefing": (
            "Narração de documentário. Tom de autoridade calma, terceira pessoa. Cada parágrafo "
            "abre um plano visual ('enquanto isso, a 400 quilômetros dali…'). Explica causa e "
            "consequência. Sem gírias, sem CTA de rede social. Frases médias com uma pausa clara "
            "no meio."
        ),
        "expressividade": 0.15,
        "velocidade": "0.9",
    },
    {
        "id": "curiosidades",
        "label": "Curiosidades / Lista",
        "emoji": "🤯",
        "resumo": "Fatos em sequência rápida, um choque a cada 4 segundos.",
        "ritmo": "rápido",
        "briefing": (
            "Vídeo de curiosidades em lista. Gancho na primeira linha com o fato mais absurdo. "
            "Depois um fato por bloco, cada bloco com no máximo duas frases. Sem enrolação entre "
            "os itens. Usa contraste ('você acha X, mas…'). Fecha com o fato mais forte guardado "
            "para o final."
        ),
        "expressividade": 0.3,
        "velocidade": "1.1",
    },
    {
        "id": "storytime",
        "label": "Storytime pessoal",
        "emoji": "💬",
        "resumo": "Conversa de amigo: começa pelo clímax e volta pra explicar.",
        "ritmo": "médio",
        "briefing": (
            "Storytime em primeira pessoa, linguagem falada do dia a dia. Começa pelo clímax "
            "('quando eu percebi, já era tarde') e só depois volta e explica. Pode usar 'aí', "
            "'sério', 'olha só'. Frases curtas. Sem palavra difícil. Termina com a lição ou com "
            "um gancho para a parte 2."
        ),
        "expressividade": 0.45,
        "velocidade": "1",
    },
    {
        "id": "motivacional",
        "label": "Motivacional",
        "emoji": "🔥",
        "resumo": "Confronto, virada e ordem final. Frases marteladas.",
        "ritmo": "médio",
        "briefing": (
            "Discurso motivacional. Abre confrontando o espectador com uma verdade incômoda. "
            "Usa segunda pessoa ('você'). Frases curtas, marteladas, com repetição proposital de "
            "uma palavra-chave. Constrói em três degraus: dor, virada, ordem. Termina com uma "
            "ordem de uma linha. Zero clichê genérico de coach."
        ),
        "expressividade": 0.45,
        "velocidade": "1",
    },
    {
        "id": "oferta",
        "label": "Oferta direta (VSL)",
        "emoji": "💰",
        "resumo": "Problema, mecanismo, prova e chamada — sem rodeio.",
        "ritmo": "rápido",
        "briefing": (
            "Copy de oferta direta para vídeo curto. Estrutura: problema específico, custo de não "
            "resolver, mecanismo único, prova, chamada para ação clara. Fala com uma pessoa só. "
            "Sem promessa de resultado garantido e sem dado inventado — só usa números que já "
            "estejam no texto original."
        ),
        "expressividade": 0.3,
        "velocidade": "1.1",
    },
    {
        "id": "tutorial",
        "label": "Tutorial / Passo a passo",
        "emoji": "🛠️",
        "resumo": "Resultado primeiro, depois os passos numerados.",
        "ritmo": "médio",
        "briefing": (
            "Tutorial narrado. Primeira linha entrega o resultado final. Depois os passos, um por "
            "bloco, começando com verbo no imperativo. Avisa o erro comum de cada passo em uma "
            "frase. Termina com o resultado esperado. Sem introdução longa."
        ),
        "expressividade": 0.15,
        "velocidade": "1",
    },
    {
        "id": "conspiracao",
        "label": "Mistério / Conspiração",
        "emoji": "👁️",
        "resumo": "Sussurro de quem sabe demais: pergunta, pista, dúvida.",
        "ritmo": "médio",
        "briefing": (
            "Narração de mistério. Tom de quem está contando algo que não deveria. Abre com uma "
            "pergunta que ninguém sabe responder. Alterna pista concreta e dúvida. Nunca afirma "
            "como fato o que é especulação: usa 'dizem que', 'os registros mostram', 'ninguém "
            "explicou até hoje'. Fecha devolvendo a pergunta ao espectador."
        ),
        "expressividade": 0.45,
        "velocidade": "0.9",
    },
    {
        "id": "asmr",
        "label": "ASMR / Calmo",
        "emoji": "🌙",
        "resumo": "Voz baixa, frases longas e macias, zero sobressalto.",
        "ritmo": "lento",
        "briefing": (
            "Narração calma para relaxamento. Frases longas e suaves, sem exclamação, sem palavra "
            "agressiva. Muita descrição sensorial macia. Ritmo constante, com reticências marcando "
            "pausas. Nada de gancho agressivo nem CTA."
        ),
        "expressividade": 0,
        "velocidade": "0.9",
    },
    {
        "id": "esporte",
        "label": "Narração esportiva",
        "emoji": "🏟️",
        "resumo": "Locução de jogo: aceleração até o grito.",
        "ritmo": "rápido",
        "briefing": (
            "Locução esportiva. Presente do indicativo, frases cada vez mais curtas conforme a "
            "tensão sobe. Nomes e números ditos por extenso. O momento de clímax vira uma linha "
            "isolada. Depois do clímax, uma frase longa de respiro comentando o feito."
        ),
        "expressividade": 0.45,
        "velocidade": "1.1",
    },
    {
        "id": "comedia",
        "label": "Comédia / Roast",
        "emoji": "😂",
        "resumo": "Setup curto, punch curtíssimo, sem explicar a piada.",
        "ritmo": "rápido",
        "briefing": (
            "Narração de humor. Setup curto e punchline mais curta ainda. Nunca explica a piada. "
            "Usa exagero e comparação inesperada. Uma piada a cada 2 ou 3 frases. Sem ofensa a "
            "grupo, religião ou característica física."
        ),
        "expressividade": 0.45,
        "velocidade": "1.1",
    },
    {
        "id": "neutro",
        "label": "Neutro (só corrigir)",
        "emoji": "✅",
        "resumo": "Mantém o texto como está e só arruma o que atrapalha a narração.",
        "ritmo": "médio",
        "briefing": (
            "Não mude o estilo nem o conteúdo. Apenas corrija ortografia, pontuação, concordância "
            "e quebre frases longas demais para caberem em uma respiração. Preserve as palavras "
            "do autor sempre que possível."
        ),
        "expressividade": 0.15,
        "velocidade": "1",
    },
]

STYLE_IDS = tuple(s["id"] for s in STYLES)

# Ações rápidas do chat: cada uma vira uma instrução extra para o LLM.
ACTIONS: list[dict[str, str]] = [
    {"id": "corrigir", "label": "Corrigir", "hint": "Gramática, pontuação e fluidez para leitura em voz alta."},
    {"id": "reescrever", "label": "Reescrever no estilo", "hint": "Aplica o estilo narrativo escolhido do início ao fim."},
    {"id": "gancho", "label": "Melhorar o gancho", "hint": "Refaz os 3 primeiros segundos para segurar o espectador."},
    {"id": "encurtar", "label": "Encurtar", "hint": "Corta o excesso mantendo a informação."},
    {"id": "alongar", "label": "Alongar", "hint": "Desenvolve o roteiro sem inventar fato novo."},
    {"id": "cta", "label": "Fechar com CTA", "hint": "Adiciona um encerramento com chamada para ação."},
]
ACTION_IDS = tuple(a["id"] for a in ACTIONS)

_ACTION_PROMPT = {
    "corrigir": "Corrija o texto para leitura em voz alta sem mudar o sentido nem o estilo do autor.",
    "reescrever": "Reescreva o texto inteiro aplicando o estilo narrativo descrito acima.",
    "gancho": "Reescreva as duas primeiras frases para criar um gancho irresistível e mantenha o resto coerente.",
    "encurtar": "Reduza o texto em cerca de 30% mantendo todas as informações essenciais.",
    "alongar": "Desenvolva o texto em cerca de 40% a mais, sem inventar nenhum fato novo.",
    "cta": "Mantenha o texto e adicione um encerramento curto com chamada para ação coerente com o estilo.",
}

# Muletas que só atrapalham a locução (o LLM tira; a correção local também).
_FILLERS = [
    "basicamente", "literalmente", "na verdade assim", "tipo assim",
    "é importante ressaltar que", "vale lembrar que", "sem mais delongas",
    "como podemos ver", "nesse sentido", "por assim dizer",
]

_ORDINALS = {
    "1º": "primeiro", "2º": "segundo", "3º": "terceiro", "4º": "quarto", "5º": "quinto",
    "1ª": "primeira", "2ª": "segunda", "3ª": "terceira", "4ª": "quarta", "5ª": "quinta",
}

_ABBREV = {
    r"\bvc\b": "você", r"\bpq\b": "porque", r"\btb\b": "também", r"\bqd\b": "quando",
    r"\bhj\b": "hoje", r"\bmt\b": "muito", r"\bq\b": "que", r"\bpra\b": "para",
    r"\bnº\b": "número", r"\betc\.?\b": "e por aí vai",
}

# Ritmo de locução: ~2,6 palavras por segundo em português falado com clareza.
WORDS_PER_SECOND = 2.6
# Acima disso a frase não cabe numa respiração confortável.
MAX_WORDS_PER_SENTENCE = 28


def list_styles() -> list[dict[str, Any]]:
    return [
        {k: v for k, v in style.items() if k != "briefing"}
        for style in STYLES
    ]


def get_style(style_id: str) -> dict[str, Any]:
    for style in STYLES:
        if style["id"] == style_id:
            return style
    return STYLES[-1]  # neutro


# --------------------------------------------------------------------------- #
# 1. Correção determinística (funciona offline)
# --------------------------------------------------------------------------- #
def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def clean_for_speech(text: str) -> str:
    """Arruma o que sempre estraga narração, sem depender de IA."""
    out = text.replace("\r\n", "\n").replace("\u00a0", " ")
    out = re.sub(r"https?://\S+", "", out)          # link não se narra
    out = re.sub(r"[*_`#>|]+", "", out)             # markdown solto
    out = re.sub(r"\s*\n\s*", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    # Pontuação: primeiro colapsa repetição, só depois normaliza espaçamento —
    # a ordem inversa transformava "!!!" em "! ! !".
    out = re.sub(r"\.{3,}", "…", out)
    out = re.sub(r"([!?])\1+", r"\1", out)
    out = re.sub(r"([,;:.])\1+", r"\1", out)
    out = re.sub(r"\s+([,.;:!?…])", r"\1", out)
    out = re.sub(r"([,.;:!?…])(?=[^\s\d,.;:!?…])", r"\1 ", out)

    for pattern, replacement in _ABBREV.items():
        out = re.sub(pattern, replacement, out, flags=re.IGNORECASE)
    for old, new in _ORDINALS.items():
        out = out.replace(old, new)
    for filler in _FILLERS:
        out = re.sub(rf"\b{re.escape(filler)}\b[,]?\s*", "", out, flags=re.IGNORECASE)

    # Depois de cortar muleta a frase pode começar em minúscula.
    out = re.sub(r"(^|[.!?…]\s+)([a-zà-ÿ])", lambda m: m.group(1) + m.group(2).upper(), out)

    out = re.sub(r"([0-9])%", r"\1 por cento", out)
    out = re.sub(r"\bkm/h\b", "quilômetros por hora", out)

    # Uma frase por respiração: quebra parágrafos gigantes em blocos de 2 frases.
    blocks: list[str] = []
    for paragraph in out.split("\n\n"):
        sentences = _split_sentences(paragraph)
        if not sentences:
            continue
        if len(sentences) <= 3:
            blocks.append(" ".join(sentences))
            continue
        for i in range(0, len(sentences), 2):
            blocks.append(" ".join(sentences[i : i + 2]))
    out = "\n\n".join(blocks)
    return out.strip()


def analyze(text: str) -> dict[str, Any]:
    """Diagnóstico numérico do roteiro — o mesmo que o painel do chat mostra."""
    sentences = _split_sentences(text)
    words = re.findall(r"[\wÀ-ÿ'-]+", text)
    long_sentences = [s for s in sentences if len(s.split()) > MAX_WORDS_PER_SENTENCE]
    digits = re.findall(r"(?<![\w])\d{2,}(?![\w])", text)
    caps = re.findall(r"\b[A-ZÀ-Ý]{3,}\b", text)
    fillers = [f for f in _FILLERS if re.search(rf"\b{re.escape(f)}\b", text, re.IGNORECASE)]
    first = sentences[0] if sentences else ""

    problems: list[str] = []
    if not text.strip():
        problems.append("Roteiro vazio.")
    if long_sentences:
        problems.append(
            f"{len(long_sentences)} frase(s) com mais de {MAX_WORDS_PER_SENTENCE} palavras — "
            "o narrador fica sem ar."
        )
    if len(first.split()) > 14:
        problems.append("O gancho tem mais de 14 palavras; nos 3 primeiros segundos isso não cabe.")
    if digits:
        problems.append(
            f"{len(digits)} número(s) em algarismo ({', '.join(digits[:4])}…) — "
            "escreva por extenso para o TTS não errar."
        )
    if caps:
        problems.append(f"Palavra(s) em CAIXA ALTA ({', '.join(caps[:3])}) podem virar soletração.")
    if fillers:
        problems.append(f"Muletas encontradas: {', '.join(fillers[:4])}.")
    if "\n" not in text.strip() and len(words) > 90:
        problems.append("Texto num bloco único: separe em parágrafos para dar respiro.")

    return {
        "words": len(words),
        "sentences": len(sentences),
        "chars": len(text),
        "estimated_seconds": round(len(words) / WORDS_PER_SECOND, 1),
        "avg_words_per_sentence": round(len(words) / len(sentences), 1) if sentences else 0,
        "hook": first[:160],
        "problems": problems,
    }


# --------------------------------------------------------------------------- #
# 2. Reescrita por IA
# --------------------------------------------------------------------------- #
_ROUTES = [
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat"),
    ("mistral", "https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
    ("siliconflow", "https://api.siliconflow.com/v1/chat/completions", "deepseek-ai/DeepSeek-V3"),
]


def llm_available() -> bool:
    return any(api_keys.get_key(pid) for pid, _u, _m in _ROUTES)


def _system_prompt(style: dict[str, Any], seconds: int | None) -> str:
    limit = ""
    if seconds:
        limit = (
            f"\nO roteiro final precisa caber em cerca de {seconds} segundos de narração "
            f"(aproximadamente {int(seconds * WORDS_PER_SECOND)} palavras)."
        )
    return (
        "Você é roteirista de vídeo curto e diretor de locução, português do Brasil.\n"
        f"ESTILO SOLICITADO — {style['label']}:\n{style['briefing']}\n"
        "REGRAS FIXAS DE LOCUÇÃO:\n"
        "- Escreva para ser FALADO, não lido: números e siglas por extenso quando forem ditos.\n"
        f"- Nenhuma frase com mais de {MAX_WORDS_PER_SENTENCE} palavras.\n"
        "- Parágrafos curtos separados por linha em branco (cada um é uma respiração).\n"
        "- Sem markdown, sem emoji, sem título, sem rubrica entre colchetes.\n"
        "- Não invente fatos, nomes, datas ou números que não estejam no texto do usuário."
        f"{limit}\n"
        'Responda SOMENTE JSON válido: {"roteiro":"texto final","mudancas":["o que você alterou"],'
        '"observacao":"1 frase de direção de locução"}'
    )


def rewrite(
    text: str,
    *,
    style_id: str = "neutro",
    action: str = "corrigir",
    instruction: str = "",
    seconds: int | None = None,
    timeout: int = 60,
) -> dict[str, Any]:
    """Devolve o roteiro corrigido. Usa IA quando há chave; senão, correção local."""
    from .trends import _http_json  # reaproveita o cliente HTTP com retry/timeout

    style = get_style(style_id)
    base = clean_for_speech(text)
    action = action if action in ACTION_IDS else "corrigir"

    task = _ACTION_PROMPT[action]
    if instruction.strip():
        task += f"\nPedido extra do usuário: {instruction.strip()}"
    user_prompt = f"{task}\n\nTEXTO ORIGINAL:\n\"\"\"\n{text.strip()}\n\"\"\""

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
                        {"role": "system", "content": _system_prompt(style, seconds)},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7 if action != "corrigir" else 0.3,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
            content = data["choices"][0]["message"]["content"]
            start, end = content.find("{"), content.rfind("}")
            if start == -1 or end == -1:
                continue
            parsed = json.loads(content[start : end + 1])
            script = clean_for_speech(str(parsed.get("roteiro") or "").strip())
            if len(script) < 2:
                continue
            changes = [str(c) for c in (parsed.get("mudancas") or [])][:8]
            return {
                "script": script,
                "changes": changes,
                "note": str(parsed.get("observacao") or "").strip(),
                "provider": provider,
                "model": model,
                "style": style["id"],
                "action": action,
                "analysis": analyze(script),
                "fallback": False,
            }
        except Exception:  # noqa: BLE001 — provedor fora do ar: tenta o próximo
            continue

    return {
        "script": base,
        "changes": ["Correção local aplicada (pontuação, muletas, quebras de respiração)."],
        "note": (
            "Nenhum provedor de IA respondeu. Cadastre uma chave (DeepSeek, Groq, OpenRouter ou "
            "Mistral) em /apis para liberar a reescrita por estilo."
        ),
        "provider": None,
        "model": None,
        "style": style["id"],
        "action": action,
        "analysis": analyze(base),
        "fallback": True,
    }
