"""Estúdio de legendas virais — geração de ASS profissional.

Este módulo é o coração da Ferramenta 3. Ele transforma transcrições (com ou
sem timestamps por palavra) em arquivos ASS de altíssimo nível, com presets
inspirados nos formatos que mais performam em Reels/Shorts/TikTok:

* Hormozi (all-caps condensado, palavra a palavra em amarelo/verde)
* MrBeast (branco pesado, contorno grosso, pop de escala)
* TikTok clássico (caixa preta arredondada)
* Karaokê (preenchimento progressivo acompanhando a música/fala)
* Neon, Podcast Clean, Typewriter, Highlight Box, entre outros

Tudo é renderizado pelo filtro `ass` do FFmpeg, então roda 100% no servidor
(aaPanel) sem dependência de serviço externo.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable

__all__ = [
    "PRESETS",
    "PRESET_IDS",
    "ANIMATIONS",
    "POSITIONS",
    "Word",
    "Line",
    "build_ass",
    "group_words",
    "lines_from_segments",
    "parse_srt",
    "spread_words",
    "preset_catalog",
    "resolve_preset",
]


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #
@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Line:
    start: float
    end: float
    words: list[Word] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words).strip()


# --------------------------------------------------------------------------- #
# Presets virais
# --------------------------------------------------------------------------- #
# size = fração da altura do vídeo (0.062 ≈ 68px num vídeo 1080x1920)
PRESETS: list[dict[str, Any]] = [
    {
        "id": "hormozi",
        "label": "Hormozi",
        "tag": "Talking head · nº1 do mercado",
        "description": "ALL CAPS pesado, palavra a palavra com destaque amarelo. O formato mais copiado do mundo.",
        "fonts": ["Montserrat ExtraBold", "Montserrat", "Anton", "DejaVu Sans"],
        "size": 0.058,
        "primary": "FFFFFF",
        "accent": "00E5FF",  # amarelo-ouro (RGB #FFE500)
        "outline": "000000",
        "back": "000000",
        "bold": True,
        "outline_w": 6,
        "shadow": 3,
        "border_style": 1,
        "uppercase": True,
        "words_per_line": 3,
        "animation": "pop",
        "spacing": 0.5,
        "preview": {"bg": "#0b0b0f", "color": "#ffffff", "accent": "#ffe500", "weight": 900, "italic": False, "boxed": False},
    },
    {
        "id": "beast",
        "label": "MrBeast",
        "tag": "Máxima energia",
        "description": "Branco maciço com contorno grosso e sombra, escala pulsando a cada palavra.",
        "fonts": ["Impact", "Anton", "Montserrat ExtraBold", "DejaVu Sans"],
        "size": 0.066,
        "primary": "FFFFFF",
        "accent": "2BE2FF",
        "outline": "000000",
        "back": "000000",
        "bold": True,
        "outline_w": 8,
        "shadow": 4,
        "border_style": 1,
        "uppercase": True,
        "words_per_line": 2,
        "animation": "bounce",
        "spacing": 0.8,
        "preview": {"bg": "#101017", "color": "#ffffff", "accent": "#ffe22b", "weight": 900, "italic": False, "boxed": False},
    },
    {
        "id": "karaoke",
        "label": "Karaokê Musical",
        "tag": "Acompanha a música",
        "description": "Preenchimento progressivo sílaba a sílaba — perfeito para clipes com música e letra.",
        "fonts": ["Montserrat", "DejaVu Sans"],
        "size": 0.052,
        "primary": "FFFFFF",
        "accent": "FF4BD8",
        "outline": "1A0022",
        "back": "000000",
        "bold": True,
        "outline_w": 4,
        "shadow": 1,
        "border_style": 1,
        "uppercase": False,
        "words_per_line": 6,
        "animation": "karaoke",
        "spacing": 0.2,
        "preview": {"bg": "#12001f", "color": "#ffffff", "accent": "#d84bff", "weight": 800, "italic": False, "boxed": False},
    },
    {
        "id": "tiktok",
        "label": "TikTok Clássico",
        "tag": "Nativo da plataforma",
        "description": "Texto branco sobre caixa preta arredondada, igual ao editor nativo do TikTok.",
        "fonts": ["Proxima Nova", "Montserrat", "DejaVu Sans"],
        "size": 0.040,
        "primary": "FFFFFF",
        "accent": "FFFFFF",
        "outline": "000000",
        "back": "000000",
        "bold": True,
        "outline_w": 6,
        "shadow": 0,
        "border_style": 4,
        "uppercase": False,
        "words_per_line": 7,
        "animation": "fade",
        "spacing": 0,
        "preview": {"bg": "#101014", "color": "#ffffff", "accent": "#ffffff", "weight": 700, "italic": False, "boxed": True},
    },
    {
        "id": "neon",
        "label": "Neon Punch",
        "tag": "Night / gaming",
        "description": "Glow roxo-neon com contorno duplo. Domina fundos escuros e clipes noturnos.",
        "fonts": ["Montserrat", "DejaVu Sans"],
        "size": 0.054,
        "primary": "FFFFFF",
        "accent": "F65CF6",
        "outline": "50004F",
        "back": "8B00FF",
        "bold": True,
        "outline_w": 4,
        "shadow": 5,
        "border_style": 1,
        "uppercase": True,
        "words_per_line": 3,
        "animation": "highlight",
        "spacing": 0.6,
        "preview": {"bg": "#0d0320", "color": "#ffffff", "accent": "#f65cf6", "weight": 800, "italic": False, "boxed": False},
    },
    {
        "id": "green_pop",
        "label": "Green Pop",
        "tag": "Conversão / oferta",
        "description": "Palavra ativa em verde-lima estourando de escala. Ideal para CTA e prova social.",
        "fonts": ["Montserrat ExtraBold", "Montserrat", "DejaVu Sans"],
        "size": 0.058,
        "primary": "FFFFFF",
        "accent": "3BFF6A",
        "outline": "000000",
        "back": "000000",
        "bold": True,
        "outline_w": 6,
        "shadow": 2,
        "border_style": 1,
        "uppercase": True,
        "words_per_line": 3,
        "animation": "pop",
        "spacing": 0.4,
        "preview": {"bg": "#04140a", "color": "#ffffff", "accent": "#6aff3b", "weight": 900, "italic": False, "boxed": False},
    },
    {
        "id": "boxed_word",
        "label": "Highlight Box",
        "tag": "Podcast viral",
        "description": "Cada palavra falada ganha uma caixa colorida atrás. Leitura instantânea no mute.",
        "fonts": ["Montserrat", "DejaVu Sans"],
        "size": 0.048,
        "primary": "FFFFFF",
        "accent": "3B82F6",
        "outline": "000000",
        "back": "F65C8B",
        "bold": True,
        "outline_w": 5,
        "shadow": 0,
        "border_style": 1,
        "uppercase": True,
        "words_per_line": 4,
        "animation": "boxed",
        "spacing": 0.3,
        "preview": {"bg": "#0b1220", "color": "#ffffff", "accent": "#3b82f6", "weight": 800, "italic": False, "boxed": True},
    },
    {
        "id": "typewriter",
        "label": "Typewriter",
        "tag": "Storytelling",
        "description": "Frase revelada palavra por palavra, sem sumir. Segura o olhar em narrativas longas.",
        "fonts": ["DejaVu Sans Mono", "JetBrains Mono", "DejaVu Sans"],
        "size": 0.040,
        "primary": "FFFFFF",
        "accent": "00E5FF",
        "outline": "000000",
        "back": "000000",
        "bold": False,
        "outline_w": 3,
        "shadow": 1,
        "border_style": 1,
        "uppercase": False,
        "words_per_line": 6,
        "animation": "typewriter",
        "spacing": 0,
        "preview": {"bg": "#07110d", "color": "#e6fff2", "accent": "#22c55e", "weight": 500, "italic": False, "boxed": False},
    },
    {
        "id": "clean",
        "label": "Clean Impact",
        "tag": "Marca / corporativo",
        "description": "Sans branca discreta com contorno fino. Não compete com o vídeo, só entrega leitura.",
        "fonts": ["Inter", "Montserrat", "DejaVu Sans"],
        "size": 0.036,
        "primary": "FFFFFF",
        "accent": "FFFFFF",
        "outline": "000000",
        "back": "000000",
        "bold": False,
        "outline_w": 2,
        "shadow": 1,
        "border_style": 1,
        "uppercase": False,
        "words_per_line": 8,
        "animation": "fade",
        "spacing": 0,
        "preview": {"bg": "#12151c", "color": "#ffffff", "accent": "#cbd5f5", "weight": 600, "italic": False, "boxed": False},
    },
    {
        "id": "golden",
        "label": "Golden Frame",
        "tag": "Luxo / finanças",
        "description": "Dourado com contorno escuro e leve itálico. Vibe premium para nicho de dinheiro.",
        "fonts": ["Playfair Display", "Montserrat", "DejaVu Serif", "DejaVu Sans"],
        "size": 0.050,
        "primary": "9FD8FF",  # dourado (RGB #FFD89F)
        "accent": "00D7FF",
        "outline": "0B0B0B",
        "back": "000000",
        "bold": True,
        "outline_w": 4,
        "shadow": 2,
        "border_style": 1,
        "uppercase": False,
        "words_per_line": 5,
        "animation": "highlight",
        "spacing": 0.4,
        "italic": True,
        "preview": {"bg": "#15100a", "color": "#ffd89f", "accent": "#ffd700", "weight": 700, "italic": True, "boxed": False},
    },
    {
        "id": "aqua",
        "label": "Aqua Edge",
        "tag": "Lifestyle / viagem",
        "description": "Ciano gelado com contorno azul-noite. Excelente em praia, céu e cenas claras.",
        "fonts": ["Montserrat", "DejaVu Sans"],
        "size": 0.050,
        "primary": "FFFFFF",
        "accent": "FFE55C",
        "outline": "5A1E00",
        "back": "000000",
        "bold": True,
        "outline_w": 5,
        "shadow": 2,
        "border_style": 1,
        "uppercase": True,
        "words_per_line": 3,
        "animation": "pop",
        "spacing": 0.4,
        "preview": {"bg": "#04141c", "color": "#ffffff", "accent": "#5ce5ff", "weight": 800, "italic": False, "boxed": False},
    },
    {
        "id": "comic",
        "label": "Comic Burst",
        "tag": "Humor / reação",
        "description": "Contorno grosso estilo HQ com sacudida a cada palavra. Feito para cortes de comédia.",
        "fonts": ["Comic Neue", "Impact", "DejaVu Sans"],
        "size": 0.060,
        "primary": "FFFFFF",
        "accent": "2B2BFF",
        "outline": "000000",
        "back": "000000",
        "bold": True,
        "outline_w": 7,
        "shadow": 3,
        "border_style": 1,
        "uppercase": True,
        "words_per_line": 2,
        "animation": "shake",
        "spacing": 0.8,
        "preview": {"bg": "#1a0c0c", "color": "#ffffff", "accent": "#ff2b2b", "weight": 900, "italic": False, "boxed": False},
    },
]

PRESET_IDS = tuple(p["id"] for p in PRESETS)
_PRESET_MAP = {p["id"]: p for p in PRESETS}

ANIMATIONS = (
    "auto",
    "none",
    "pop",
    "bounce",
    "fade",
    "karaoke",
    "typewriter",
    "highlight",
    "boxed",
    "shake",
    # --- pacote viral 2024/2025 (referências: Hormozi, MrBeast, Submagic,
    # CapCut "Beat Sync", Opus Clip, VEED, Captions.ai) ---
    "beat",       # pulso forte na batida — feito para usar com beat_sync
    "zoom",       # zoom punch: entra grande e crava
    "slide",      # sobe deslizando com fade
    "blur",       # desfoque que entra em foco
    "wave",       # onda: palavras sobem e descem alternando
    "glitch",     # split RGB estilo glitch
    "neon",       # brilho neon pulsante no contorno
    "rainbow",    # cada palavra em uma cor do ciclo
    "stamp",      # carimbo: gira e crava
    "flip",       # vira no eixo Y
)

# Animações que precisam saber a posição da palavra na linha
_INDEXED_ANIMS = {"wave", "rainbow"}

# Ciclo de cores do modo rainbow (BBGGRR, como o ASS espera)
_RAINBOW = ("&H0000FF&", "&H00A5FF&", "&H00FFFF&", "&H00FF00&", "&HFFFF00&", "&HFF00FF&")
POSITIONS = {"bottom": 2, "center": 5, "top": 8}

# Compatibilidade com os estilos antigos da ferramenta.
LEGACY_ALIASES = {"viral": "hormozi", "clean": "clean", "neon": "neon", "karaoke": "karaoke"}


def resolve_preset(preset_id: str | None) -> dict[str, Any]:
    key = (preset_id or "").strip().lower()
    key = LEGACY_ALIASES.get(key, key)
    return _PRESET_MAP.get(key, _PRESET_MAP["hormozi"])


def preset_catalog() -> list[dict[str, Any]]:
    """Catálogo enxuto para o frontend montar a galeria."""
    return [
        {
            "id": p["id"],
            "label": p["label"],
            "tag": p["tag"],
            "description": p["description"],
            "animation": p["animation"],
            "uppercase": p["uppercase"],
            "words_per_line": p["words_per_line"],
            "preview": p["preview"],
        }
        for p in PRESETS
    ]


# --------------------------------------------------------------------------- #
# Fontes disponíveis no servidor
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _installed_fonts() -> set[str]:
    try:
        out = subprocess.run(  # noqa: S603
            ["fc-list", ":", "family"], capture_output=True, text=True, timeout=20, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    families: set[str] = set()
    for line in out.splitlines():
        for part in line.split(","):
            name = part.strip()
            if name:
                families.add(name.lower())
    return families


def pick_font(candidates: Iterable[str]) -> str:
    installed = _installed_fonts()
    options = list(candidates)
    if not installed:
        return options[-1] if options else "DejaVu Sans"
    for name in options:
        if name.lower() in installed:
            return name
    return "DejaVu Sans"


# --------------------------------------------------------------------------- #
# Cores
# --------------------------------------------------------------------------- #
def _ass_color(value: str, alpha: str = "00") -> str:
    """Aceita 'RRGGBB', '#RRGGBB' ou já 'BBGGRR' de 6 dígitos e devolve &HAABBGGRR."""
    raw = (value or "").strip().lstrip("#")
    if len(raw) != 6 or not re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
        raw = "FFFFFF"
    return f"&H{alpha}{raw.upper()}&"


def hex_rgb_to_ass(value: str) -> str:
    """Converte '#RRGGBB' (frontend) para a ordem BBGGRR usada nos presets."""
    raw = (value or "").strip().lstrip("#")
    if len(raw) != 6 or not re.fullmatch(r"[0-9A-Fa-f]{6}", raw):
        return ""
    return (raw[4:6] + raw[2:4] + raw[0:2]).upper()


# --------------------------------------------------------------------------- #
# Entrada: SRT e segmentos
# --------------------------------------------------------------------------- #
_TS = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")


def _parse_ts(value: str) -> float:
    m = _TS.search(value)
    if not m:
        return 0.0
    h, mm, ss, ms = m.groups()
    return int(h) * 3600 + int(mm) * 60 + int(ss) + int(ms.ljust(3, "0")) / 1000


def parse_srt(text: str) -> list[Line]:
    """Converte SRT em linhas (sem timing por palavra — distribuído depois)."""
    lines: list[Line] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        rows = [r.strip() for r in block.splitlines() if r.strip()]
        if not rows:
            continue
        if rows[0].isdigit():
            rows = rows[1:]
        if not rows or "-->" not in rows[0]:
            continue
        left, _, right = rows[0].partition("-->")
        start, end = _parse_ts(left), _parse_ts(right)
        content = " ".join(rows[1:]).strip()
        if not content or end <= start:
            continue
        lines.append(Line(start=start, end=end, words=_spread_words(content, start, end)))
    return lines


def _spread_words(text: str, start: float, end: float) -> list[Word]:
    """Distribui o tempo da linha entre as palavras proporcionalmente ao tamanho."""
    tokens = [t for t in text.split() if t]
    if not tokens:
        return []
    total_chars = sum(len(t) for t in tokens) or 1
    span = max(0.2, end - start)
    words: list[Word] = []
    cursor = start
    for token in tokens:
        share = span * (len(token) / total_chars)
        words.append(Word(start=cursor, end=min(end, cursor + share), text=token))
        cursor += share
    words[-1].end = end
    return words


def group_words(
    words: list[Word], *, max_words: int, max_chars: int = 42, max_gap: float = 0.65
) -> list[Line]:
    """Agrupa palavras em linhas curtas, quebrando em pausas naturais."""
    lines: list[Line] = []
    bucket: list[Word] = []

    def flush() -> None:
        nonlocal bucket
        if bucket:
            lines.append(Line(start=bucket[0].start, end=bucket[-1].end, words=bucket))
            bucket = []

    for word in words:
        if bucket:
            gap = word.start - bucket[-1].end
            chars = sum(len(w.text) + 1 for w in bucket) + len(word.text)
            ends_sentence = bucket[-1].text.endswith((".", "!", "?", "…"))
            if len(bucket) >= max_words or chars > max_chars or gap > max_gap or ends_sentence:
                flush()
        bucket.append(word)
    flush()
    return lines


def lines_from_segments(segments: list[Any], *, max_words: int) -> list[Line]:
    """Aceita objetos com .start/.end/.text (e opcionalmente .words)."""
    words: list[Word] = []
    for seg in segments:
        raw_words = getattr(seg, "words", None) or []
        if raw_words:
            for w in raw_words:
                text = str(getattr(w, "text", "") or "").strip()
                if not text:
                    continue
                words.append(
                    Word(
                        start=float(getattr(w, "start", 0.0)),
                        end=float(getattr(w, "end", 0.0)) or float(getattr(w, "start", 0.0)) + 0.25,
                        text=text,
                    )
                )
        else:
            words.extend(
                _spread_words(
                    str(getattr(seg, "text", "") or ""),
                    float(getattr(seg, "start", 0.0)),
                    float(getattr(seg, "end", 0.0)),
                )
            )
    words = [w for w in words if w.text]
    words.sort(key=lambda w: w.start)
    # Corrige sobreposições
    for prev, nxt in zip(words, words[1:]):
        if prev.end > nxt.start:
            prev.end = max(prev.start + 0.08, nxt.start)
    return group_words(words, max_words=max_words)


# --------------------------------------------------------------------------- #
# Geração do ASS
# --------------------------------------------------------------------------- #
def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def build_ass(
    lines: list[Line],
    *,
    preset_id: str,
    video_width: int,
    video_height: int,
    position: str = "bottom",
    animation: str = "auto",
    uppercase: bool | None = None,
    font_scale: float = 1.0,
    accent_hex: str = "",
    primary_hex: str = "",
    margin_ratio: float = 0.14,
    emoji: bool = False,
) -> str:
    preset = resolve_preset(preset_id)
    width = max(64, int(video_width or 1080))
    height = max(64, int(video_height or 1920))
    anim = animation if animation in ANIMATIONS and animation != "auto" else preset["animation"]
    upper = preset["uppercase"] if uppercase is None else bool(uppercase)

    font = pick_font(preset["fonts"])
    size = max(12, int(height * float(preset["size"]) * max(0.5, min(2.0, font_scale))))
    align = POSITIONS.get(position, 2)
    margin_v = int(height * (margin_ratio if align == 2 else 0.08)) if align != 5 else 10
    margin_h = int(width * 0.06)

    primary_raw = hex_rgb_to_ass(primary_hex) or preset["primary"]
    accent_raw = hex_rgb_to_ass(accent_hex) or preset["accent"]
    primary = _ass_color(primary_raw)
    accent = _ass_color(accent_raw)
    outline = _ass_color(preset["outline"])
    back = _ass_color(preset["back"], alpha="40" if preset["border_style"] == 4 else "80")

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        # 0 = quebra inteligente e balanceada. Com 2 (sem quebra) frases longas
        # saem cortadas nas bordas do vídeo — bug visto em render real 1080x1920.
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour,"
        " Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline,"
        " Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        (
            f"Style: Viral,{font},{size},{primary},{accent},{outline},{back},"
            f"{-1 if preset['bold'] else 0},{-1 if preset.get('italic') else 0},0,0,100,100,"
            f"{preset['spacing']},0,{preset['border_style']},{preset['outline_w']},{preset['shadow']},"
            f"{align},{margin_h},{margin_h},{margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    events: list[str] = []
    for line in lines:
        events.extend(
            _render_line(line, anim=anim, upper=upper, accent=accent, primary=primary, emoji=emoji)
        )

    return "\n".join(header + events) + "\n"


def _dialogue(start: float, end: float, text: str) -> str:
    return f"Dialogue: 0,{_ts(start)},{_ts(end)},Viral,,0,0,0,,{text}"


_EMOJI_HINTS = (
    (("dinheiro", "grana", "lucro", "rico", "milhão", "faturar"), "💰"),
    (("segredo", "ninguém", "verdade"), "🤫"),
    (("rápido", "agora", "urgente", "corre"), "⚡"),
    (("atenção", "cuidado", "erro", "pare"), "🚨"),
    (("crescer", "viral", "bombar", "explodir"), "🚀"),
    (("amor", "coração", "família"), "❤️"),
)


def _maybe_emoji(text: str) -> str:
    low = text.lower()
    for keys, icon in _EMOJI_HINTS:
        if any(k in low for k in keys):
            return f"{text} {icon}"
    return text


def _render_line(
    line: Line, *, anim: str, upper: bool, accent: str, primary: str, emoji: bool
) -> list[str]:
    words = [w for w in line.words if w.text.strip()]
    if not words:
        return []

    def render(text: str) -> str:
        out = text.upper() if upper else text
        return _escape(out)

    start, end = line.start, max(line.end, line.start + 0.25)

    if anim in {"none", "fade"}:
        prefix = "{\\fad(90,90)}" if anim == "fade" else ""
        body = " ".join(render(w.text) for w in words)
        if emoji:
            body = _maybe_emoji(body)
        return [_dialogue(start, end, prefix + body)]

    if anim == "karaoke":
        chunks: list[str] = []
        for w in words:
            duration_cs = max(5, int(round((w.end - w.start) * 100)))
            chunks.append(f"{{\\kf{duration_cs}}}{render(w.text)}")
        return [_dialogue(start, end, "{\\fad(60,60)}" + " ".join(chunks))]

    if anim == "typewriter":
        events: list[str] = []
        for index, word in enumerate(words):
            visible = " ".join(render(w.text) for w in words[: index + 1])
            hidden = " ".join(render(w.text) for w in words[index + 1 :])
            text = visible + (f" {{\\alpha&HFF&}}{hidden}" if hidden else "")
            stop = words[index + 1].start if index + 1 < len(words) else end
            events.append(_dialogue(word.start, max(word.start + 0.06, stop), text))
        return events

    # Modos palavra a palavra (pop, bounce, highlight, boxed, shake)
    events = []
    for index, word in enumerate(words):
        parts: list[str] = []
        for other_index, other in enumerate(words):
            token = render(other.text)
            if other_index == index:
                token = _active_token(
                    token,
                    anim=anim,
                    accent=accent,
                    primary=primary,
                    index=index,
                    total=len(words),
                )
            parts.append(token)
        text = " ".join(parts)
        if emoji and index == len(words) - 1:
            text = _maybe_emoji(text)
        stop = words[index + 1].start if index + 1 < len(words) else end
        events.append(_dialogue(word.start, max(word.start + 0.08, stop), text))
    return events


def _active_token(
    token: str, *, anim: str, accent: str, primary: str, index: int = 0, total: int = 1
) -> str:
    color = f"\\c{accent}"
    reset = "{\\r}"  # volta 100% ao estilo base (cor, escala, contorno, rotação)
    if anim == "pop":
        tag = f"{{{color}\\fscx118\\fscy118\\t(0,110,\\fscx100\\fscy100)}}"
    elif anim == "bounce":
        tag = f"{{{color}\\fscy132\\fscx108\\t(0,90,\\fscy96\\fscx104)\\t(90,180,\\fscy100\\fscx100)}}"
    elif anim == "shake":
        tag = f"{{{color}\\frz-4\\t(0,80,\\frz4)\\t(80,160,\\frz0)\\fscx112\\fscy112\\t(0,140,\\fscx100\\fscy100)}}"
    elif anim == "boxed":
        tag = f"{{\\c&H00FFFFFF&\\3c{accent}\\bord14\\shad0}}"
    elif anim == "beat":
        # pulso curto e seco, no tempo da batida (usar junto com beat_sync)
        tag = (
            f"{{{color}\\fscx142\\fscy142\\t(0,70,\\fscx96\\fscy96)"
            "\\t(70,150,\\fscx100\\fscy100)}"
        )
    elif anim == "zoom":
        tag = f"{{{color}\\fscx165\\fscy165\\alpha&H40&\\t(0,120,\\fscx100\\fscy100\\alpha&H00&)}}"
    elif anim == "slide":
        tag = f"{{{color}\\fay-0.12\\t(0,130,\\fay0)\\alpha&HB0&\\t(0,130,\\alpha&H00&)}}"
    elif anim == "blur":
        tag = f"{{{color}\\blur9\\t(0,160,\\blur0)\\fscx108\\fscy108\\t(0,160,\\fscx100\\fscy100)}}"
    elif anim == "wave":
        up = index % 2 == 0
        shift = "-0.10" if up else "0.10"
        tag = f"{{{color}\\fay{shift}\\t(0,180,\\fay0)\\fscy118\\t(0,180,\\fscy100)}}"
    elif anim == "glitch":
        tag = (
            f"{{{color}\\3c&H00FFFF&\\bord6\\xshad-5\\yshad0\\4c&HFF0000&"
            "\\t(0,60,\\xshad5)\\t(60,130,\\xshad0)\\fscx112\\t(0,130,\\fscx100)}"
        )
    elif anim == "neon":
        tag = (
            f"{{{color}\\3c{accent}\\bord2\\blur6\\t(0,140,\\bord9\\blur14)"
            "\\t(140,300,\\bord4\\blur7)}"
        )
    elif anim == "rainbow":
        hue = _RAINBOW[index % len(_RAINBOW)]
        tag = f"{{\\c{hue}\\fscx114\\fscy114\\t(0,140,\\fscx100\\fscy100)}}"
    elif anim == "stamp":
        tag = (
            f"{{{color}\\frz-12\\fscx170\\fscy170\\alpha&H60&"
            "\\t(0,110,\\frz0\\fscx100\\fscy100\\alpha&H00&)}"
        )
    elif anim == "flip":
        tag = f"{{{color}\\fry88\\t(0,150,\\fry0)\\fscx105\\t(0,150,\\fscx100)}}"
    else:  # highlight
        tag = f"{{{color}}}"
    # `reset` volta ao estilo base para as palavras seguintes na mesma linha
    return tag + token + reset


spread_words = _spread_words
