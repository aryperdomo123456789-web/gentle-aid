"""Voice Forge — criação de vozes próprias a partir de um motor base.

Ideia central (o pedido do operador): pegar um motor de TTS gratuito (Edge TTS)
ou o áudio já convertido e aplicar uma **assinatura acústica própria** por cima —
deslocamento de pitch, reposicionamento de formantes, curva de timbre, sopro e
ambiência. O resultado deixa de soar como a voz padrão da Microsoft e passa a ser
uma persona exclusiva do projeto, reprodutível e catalogada.

A persona é determinística: o mesmo `persona_id` gera sempre a mesma cadeia de
filtros (o "DNA" vem de um hash estável do id + seed), então a voz é consistente
entre um vídeo e outro. Duas personas nunca compartilham o mesmo micro-ajuste.

Armazenamento: JSON simples em `storage/_config/voice_personas.json`.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..config import config

_LOCK = threading.Lock()
SAMPLE_RATE = 48000

# Faixas seguras — fora disso o áudio vira robô/chipmunk.
BOUNDS = {
    "pitch": (-8.0, 8.0),        # semitons
    "formant": (0.80, 1.25),     # <1 = trato vocal maior (voz mais "grande")
    "warmth": (-8.0, 8.0),       # dB em ~180 Hz
    "brightness": (-8.0, 8.0),   # dB em ~7 kHz
    "breath": (0.0, 1.0),        # sopro/ar
    "body": (-6.0, 6.0),         # dB em ~900 Hz (corpo/nasalidade)
    "room": (0.0, 1.0),          # ambiência
    "tempo": (0.85, 1.15),
}


def _clamp(name: str, value: float) -> float:
    low, high = BOUNDS[name]
    return max(low, min(high, float(value)))


@dataclass
class Persona:
    id: str
    name: str
    base_voice: str = "pt-BR-AntonioNeural"   # voz do motor Edge TTS usada como matéria-prima
    engine: str = "edge"                       # edge | local (aplica só o DSP)
    pitch: float = -1.5
    formant: float = 0.95
    warmth: float = 2.0
    brightness: float = 1.5
    breath: float = 0.15
    body: float = 0.0
    room: float = 0.12
    tempo: float = 1.0
    rate: int = 0                              # % de velocidade no Edge TTS
    notes: str = ""
    created_at: float = field(default_factory=time.time)

    def normalized(self) -> "Persona":
        for key in BOUNDS:
            setattr(self, key, _clamp(key, getattr(self, key)))
        self.rate = max(-40, min(40, int(self.rate)))
        return self

    def dict(self) -> dict[str, object]:
        return asdict(self)


# Personas de fábrica — pontos de partida prontos, o operador ajusta a partir daí.
PRESETS: list[dict[str, object]] = [
    {
        "id": "forge_narrador_grave",
        "name": "Narrador Grave (própria)",
        "base_voice": "pt-BR-AntonioNeural",
        "pitch": -2.5, "formant": 0.92, "warmth": 3.5, "brightness": 1.0,
        "breath": 0.18, "body": 1.5, "room": 0.15, "tempo": 0.99,
        "notes": "Documentário, autoridade, cortes longos.",
    },
    {
        "id": "forge_viral_rapido",
        "name": "Viral Acelerado (própria)",
        "base_voice": "pt-BR-AntonioNeural",
        "pitch": 1.0, "formant": 1.04, "warmth": -1.0, "brightness": 4.0,
        "breath": 0.08, "body": -1.0, "room": 0.05, "tempo": 1.06, "rate": 8,
        "notes": "Reels/Shorts, ritmo alto, presença em celular.",
    },
    {
        "id": "forge_fem_suave",
        "name": "Feminina Suave (própria)",
        "base_voice": "pt-BR-FranciscaNeural",
        "pitch": 1.5, "formant": 1.08, "warmth": 2.0, "brightness": 2.5,
        "breath": 0.3, "body": 0.5, "room": 0.2, "tempo": 1.0,
        "notes": "Storytelling, bem-estar, leitura calma.",
    },
    {
        "id": "forge_misterio",
        "name": "Mistério Sussurrado (própria)",
        "base_voice": "pt-BR-AntonioNeural",
        "pitch": -4.0, "formant": 0.88, "warmth": 5.0, "brightness": -2.0,
        "breath": 0.45, "body": 2.0, "room": 0.35, "tempo": 0.96, "rate": -8,
        "notes": "True crime, curiosidades sombrias.",
    },
    # --- Persona "chiclete" -------------------------------------------------
    # Ajustada a partir da literatura de persuasão vocal, não de achismo:
    #  · Fala ~10% acima do ritmo neutro aumenta competência e persuasão
    #    percebidas sem derrubar a compreensão (Journal of Consumer Research,
    #    "Audio Mining: The Role of Vocal Tone in Persuasion", 2021).
    #  · Formante levemente elevado = "sorriso na voz": eleva simpatia e
    #    intenção de compra (Frontiers in Psychology, 2023 — fala publicitária).
    #  · Brilho em 6–8 kHz garante presença em alto-falante de celular, onde
    #    quase todo o consumo de Reels/Shorts acontece.
    #  · Sopro baixo + corpo estável = voz confiante; sopro alto lê como
    #    insegurança e derruba a confiança percebida (revisão sistemática
    #    Frontiers in Psychology, 2025, sobre acústica e trustworthiness).
    #  · Ambiência quase seca mantém o timbre "colado no ouvido" (efeito ASMR
    #    leve do "influencer voice"), sem soar gravado em sala.
    {
        "id": "forge_chiclete",
        "name": "Chiclete Persuasivo (própria)",
        "base_voice": "pt-BR-ThalitaNeural",
        "pitch": 0.9, "formant": 1.07, "warmth": 1.5, "brightness": 3.8,
        "breath": 0.09, "body": -0.5, "room": 0.05, "tempo": 1.04, "rate": 7,
        "notes": (
            "Voz-gancho para hooks e CTAs: cadência cantada de influencer, "
            "sorriso no timbre, presença de celular e ritmo ~10% acima do neutro. "
            "Gruda no ouvido e sustenta retenção nos 3 primeiros segundos."
        ),
    },
    {
        "id": "forge_chiclete_masc",
        "name": "Chiclete Persuasivo Masc. (própria)",
        "base_voice": "pt-BR-AntonioNeural",
        "pitch": -0.8, "formant": 1.03, "warmth": 2.2, "brightness": 3.2,
        "breath": 0.10, "body": 0.4, "room": 0.05, "tempo": 1.03, "rate": 6,
        "notes": (
            "Mesma engenharia do Chiclete, em registro masculino: grave o "
            "suficiente para soar confiável, brilhante e rápido o bastante "
            "para não deixar o dedo subir a tela."
        ),
    },
]



# --------------------------------------------------------------------------- #
# Persistência
# --------------------------------------------------------------------------- #
def _store_path() -> Path:
    config.config_dir.mkdir(parents=True, exist_ok=True)
    return config.config_dir / "voice_personas.json"


def _load_raw() -> dict[str, dict]:
    path = _store_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_raw(data: dict[str, dict]) -> None:
    path = _store_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _from_dict(raw: dict) -> Persona:
    allowed = {f for f in Persona.__dataclass_fields__}  # type: ignore[attr-defined]
    clean = {k: v for k, v in raw.items() if k in allowed}
    clean.setdefault("id", "forge")
    clean.setdefault("name", clean["id"])
    return Persona(**clean).normalized()


def bootstrap() -> None:
    """Garante que as personas de fábrica existam e estejam atualizadas no cofre local."""
    with _LOCK:
        data = _load_raw()
        changed = False
        for preset in PRESETS:
            pid = str(preset["id"])
            existing = data.get(pid)
            fresh = _from_dict(dict(preset)).dict()
            if existing is None:
                data[pid] = fresh
                changed = True
            else:
                # Atualiza presets de fábrica se os parâmetros melhoraram,
                # preservando created_at original para não reordenar a lista.
                preserved_created_at = float(existing.get("created_at") or fresh["created_at"])
                fresh["created_at"] = preserved_created_at
                if existing.get("name") != fresh["name"] or existing.get("base_voice") != fresh["base_voice"]:
                    data[pid] = fresh
                    changed = True
                else:
                    # Mescla campos numéricos: se o preset evoluiu, aplica novos valores.
                    numeric = {"pitch", "formant", "warmth", "brightness", "breath", "body", "room", "tempo", "rate"}
                    for key in numeric:
                        if float(existing.get(key) or 0) != float(fresh.get(key) or 0):
                            existing[key] = fresh[key]
                            changed = True
                    if existing.get("notes") != fresh.get("notes"):
                        existing["notes"] = fresh["notes"]
                        changed = True
        if changed:
            _save_raw(data)


def reset_factory_presets() -> None:
    """Recria as personas de fábrica do zero, descartando versões antigas."""
    with _LOCK:
        data = _load_raw()
        for preset in PRESETS:
            data[str(preset["id"])] = _from_dict(dict(preset)).dict()
        _save_raw(data)


def list_personas() -> list[dict[str, object]]:
    bootstrap()
    with _LOCK:
        data = _load_raw()
    personas = [_from_dict(raw).dict() for raw in data.values()]
    personas.sort(key=lambda p: (p.get("created_at") or 0))
    return personas


def get(persona_id: str) -> Persona | None:
    bootstrap()
    with _LOCK:
        raw = _load_raw().get(persona_id)
    return _from_dict(raw) if raw else None


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return f"forge_{slug or 'voz'}"[:48]


def save(payload: dict) -> Persona:
    persona = _from_dict(payload)
    if not persona.name.strip():
        raise ValueError("Dê um nome para a voz.")
    if not payload.get("id"):
        persona.id = slugify(persona.name)
    with _LOCK:
        data = _load_raw()
        if persona.id in data:
            persona.created_at = float(data[persona.id].get("created_at") or persona.created_at)
        else:
            base = persona.id
            suffix = 2
            while persona.id in data:
                persona.id = f"{base}_{suffix}"
                suffix += 1
        data[persona.id] = persona.dict()
        _save_raw(data)
    return persona


def delete(persona_id: str) -> bool:
    with _LOCK:
        data = _load_raw()
        if persona_id not in data:
            return False
        data.pop(persona_id)
        _save_raw(data)
    return True


# --------------------------------------------------------------------------- #
# Fábrica de modelos — várias vozes derivadas de uma mesma matéria-prima
# --------------------------------------------------------------------------- #
# Cada arquétipo é uma "direção" de mutação: aplicado sobre a voz base, produz um
# modelo com caráter distinto mas ainda coerente com a matéria-prima escolhida.
ARCHETYPES: list[dict[str, object]] = [
    {"key": "grave", "label": "Grave", "pitch": -2.6, "formant": -0.06, "warmth": 3.0,
     "brightness": -0.5, "breath": 0.05, "body": 1.5, "room": 0.05, "tempo": -0.02, "rate": -4},
    {"key": "jovem", "label": "Jovem", "pitch": 2.2, "formant": 0.07, "warmth": -1.5,
     "brightness": 3.0, "breath": 0.05, "body": -1.0, "room": 0.0, "tempo": 0.03, "rate": 6},
    {"key": "locutor", "label": "Locutor", "pitch": -1.0, "formant": -0.03, "warmth": 2.5,
     "brightness": 2.0, "breath": 0.0, "body": 1.0, "room": 0.10, "tempo": 0.0, "rate": 0},
    {"key": "intimo", "label": "Íntimo", "pitch": -1.8, "formant": -0.02, "warmth": 4.0,
     "brightness": -1.0, "breath": 0.35, "body": 1.0, "room": 0.25, "tempo": -0.03, "rate": -6},
    {"key": "energetico", "label": "Energético", "pitch": 1.2, "formant": 0.03, "warmth": -0.5,
     "brightness": 4.0, "breath": -0.05, "body": -0.5, "room": 0.02, "tempo": 0.05, "rate": 10},
    {"key": "cinema", "label": "Cinematográfico", "pitch": -3.4, "formant": -0.08, "warmth": 5.0,
     "brightness": 1.0, "breath": 0.20, "body": 2.0, "room": 0.32, "tempo": -0.04, "rate": -8},
    {"key": "claro", "label": "Claro / Didático", "pitch": 0.4, "formant": 0.02, "warmth": 1.0,
     "brightness": 2.5, "breath": 0.10, "body": 0.0, "room": 0.06, "tempo": 0.01, "rate": 2},
    {"key": "rouco", "label": "Rouco", "pitch": -2.0, "formant": -0.05, "warmth": 2.0,
     "brightness": 0.5, "breath": 0.55, "body": 2.5, "room": 0.12, "tempo": -0.01, "rate": -2},
]

ARCHETYPE_KEYS = [str(a["key"]) for a in ARCHETYPES]
MAX_VARIANTS = 24


def _noise(seed: str, count: int) -> list[float]:
    """Ruído determinístico em [-1, 1] com o tamanho pedido."""
    out: list[float] = []
    counter = 0
    while len(out) < count:
        digest = hashlib.sha256(f"{seed}#{counter}".encode("utf-8")).digest()
        out.extend((byte / 127.5) - 1.0 for byte in digest)
        counter += 1
    return out[:count]


def generate_variants(
    base: Persona,
    *,
    count: int = 6,
    intensity: float = 0.6,
    seed: str | None = None,
    base_voices: list[str] | None = None,
) -> list[Persona]:
    """Deriva `count` modelos distintos a partir de uma voz base.

    A mutação combina um arquétipo (direção estética) com um jitter determinístico,
    então o mesmo `seed` sempre devolve exatamente o mesmo conjunto de vozes.
    """
    count = max(1, min(MAX_VARIANTS, int(count)))
    intensity = max(0.05, min(1.5, float(intensity)))
    seed = seed or f"{base.id}:{base.base_voice}"
    pool = [v for v in (base_voices or []) if v] or [base.base_voice]
    noise = _noise(seed, count * 10)

    variants: list[Persona] = []
    for index in range(count):
        arch = ARCHETYPES[index % len(ARCHETYPES)]
        n = noise[index * 10 : index * 10 + 10]
        cycle = index // len(ARCHETYPES)
        suffix = f" {cycle + 1}" if cycle else ""
        label = f"{base.name or 'Voz'} · {arch['label']}{suffix}"

        variant = Persona(
            id=slugify(label),
            name=label,
            base_voice=pool[index % len(pool)],
            engine=base.engine,
            pitch=base.pitch + float(arch["pitch"]) * intensity + n[0] * 0.8 * intensity,
            formant=base.formant + float(arch["formant"]) * intensity + n[1] * 0.02 * intensity,
            warmth=base.warmth + float(arch["warmth"]) * intensity + n[2] * 1.0 * intensity,
            brightness=base.brightness + float(arch["brightness"]) * intensity + n[3] * 1.0 * intensity,
            breath=base.breath + float(arch["breath"]) * intensity + n[4] * 0.06 * intensity,
            body=base.body + float(arch["body"]) * intensity + n[5] * 0.8 * intensity,
            room=base.room + float(arch["room"]) * intensity + n[6] * 0.05 * intensity,
            tempo=base.tempo + float(arch["tempo"]) * intensity + n[7] * 0.015 * intensity,
            rate=int(round(base.rate + float(arch["rate"]) * intensity + n[8] * 3 * intensity)),
            notes=f"Modelo {arch['label'].lower()} derivado de “{base.name or base.base_voice}”.",
        ).normalized()
        variants.append(variant)
    return variants


def save_many(personas: list[Persona | dict]) -> list[Persona]:
    saved: list[Persona] = []
    for item in personas:
        payload = item.dict() if isinstance(item, Persona) else dict(item)
        payload.pop("id", None)  # deixa o catálogo resolver colisões de nome
        saved.append(save(payload))
    return saved


# --------------------------------------------------------------------------- #
# DNA acústico — micro-ajustes estáveis e exclusivos por persona
# --------------------------------------------------------------------------- #
def dna(persona_id: str) -> list[float]:
    """Sequência determinística em [-1, 1] derivada do id da persona."""
    digest = hashlib.sha256(persona_id.encode("utf-8")).digest()
    return [(byte / 127.5) - 1.0 for byte in digest[:8]]



def filter_chain(persona: Persona, *, preserve_duration: bool = True) -> list[str]:
    """Cadeia FFmpeg que transforma a voz base na persona.

    Ordem: pitch → formantes → corpo/calor/brilho → sopro → ambiência → normalização.
    """
    persona = persona.normalized()
    g = dna(persona.id)

    pitch = persona.pitch + g[0] * 0.35
    formant = persona.formant * (1 + g[1] * 0.012)
    warmth = persona.warmth + g[2] * 0.6
    brightness = persona.brightness + g[3] * 0.6
    body = persona.body + g[4] * 0.5
    tempo_jitter = 1 + g[5] * 0.008

    ratio = 2 ** (pitch / 12)
    chain: list[str] = [
        f"asetrate={int(SAMPLE_RATE * ratio)}",
        f"aresample={SAMPLE_RATE}",
    ]

    tempo = (1 / ratio) if preserve_duration else 1.0
    tempo *= persona.tempo * tempo_jitter
    for step in _atempo_steps(tempo):
        chain.append(f"atempo={step:.6f}")

    # Formantes: desloca a região 1–3 kHz para simular outro trato vocal.
    formant_db = (formant - 1.0) * 22
    chain.append(f"equalizer=f={int(1300 * formant)}:width_type=h:width=700:g={formant_db:.2f}")
    chain.append(f"equalizer=f={int(2600 * formant)}:width_type=h:width=1200:g={formant_db * 0.7:.2f}")

    chain.append(f"equalizer=f=180:width_type=h:width=140:g={warmth:.2f}")
    chain.append(f"equalizer=f=900:width_type=h:width=500:g={body:.2f}")
    chain.append(f"equalizer=f=7000:width_type=h:width=3000:g={brightness:.2f}")
    chain.append("highpass=f=70")
    chain.append("lowpass=f=15000")

    if persona.breath > 0.02:
        # Compressão suave + realce de ar cria a sensação de respiração/proximidade.
        chain.append(
            f"acompressor=threshold=-22dB:ratio={2 + persona.breath * 2:.2f}:attack=8:release=180:makeup=1.5"
        )
        chain.append(f"equalizer=f=11000:width_type=h:width=4000:g={persona.breath * 4.5:.2f}")

    if persona.room > 0.02:
        decay = min(0.5, 0.18 + persona.room * 0.35)
        delay = int(24 + persona.room * 45)
        chain.append(f"aecho=0.85:0.85:{delay}:{decay:.3f}")

    chain.append("dynaudnorm=f=200:g=6:p=0.92")
    chain.append(f"aresample={SAMPLE_RATE}")
    return chain


def _atempo_steps(tempo: float) -> list[float]:
    """`atempo` só aceita 0.5–2.0; encadeia quando o fator extrapola."""
    tempo = max(0.25, min(4.0, tempo))
    steps: list[float] = []
    while tempo < 0.5:
        steps.append(0.5)
        tempo /= 0.5
    while tempo > 2.0:
        steps.append(2.0)
        tempo /= 2.0
    if abs(tempo - 1.0) > 0.0005 or not steps:
        steps.append(tempo)
    return steps
