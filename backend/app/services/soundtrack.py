"""Trilha inteligente — escolhe/gera o áudio certo e sincroniza o corte nele.

Três modos, todos livres de direitos autorais:

  * `upload`  — o operador manda o áudio (padrão antigo, continua igual);
  * `library` — o operador escolhe uma faixa da biblioteca do servidor
                (`<storage>/trilhas/*.mp3|wav|m4a...`, alimentada no aaPanel);
  * `auto`    — a IA lê o nicho + a transcrição real do vídeo, decide o
                *perfil sonoro viral* (estilo, BPM, energia) e escolhe a melhor
                faixa da biblioteca. Se a biblioteca não tiver nada que encaixe,
                o motor **sintetiza** a trilha no perfil escolhido com o próprio
                FFmpeg (kick + sub + hats + pad), o que é 100% original e sem
                qualquer risco de copyright/Content ID.

Toda faixa devolvida vem com BPM medido (`beatsync.detect_beats`) e com o
primeiro ataque forte marcado, para o `clipper` cortar e pulsar no tempo.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import config
from . import api_keys, beatsync

__all__ = [
    "MODES",
    "PROFILES",
    "Track",
    "library",
    "library_dir",
    "pick",
    "profile_for",
    "resolve",
    "synthesize",
]

MODES = ("none", "upload", "library", "auto", "synth")
AUDIO_SUFFIX = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac")

# Rotas de LLM na mesma ordem do resto do ecossistema (grátis → barato → reserva).
_ROUTES = [
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat"),
    ("mistral", "https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
    ("siliconflow", "https://api.siliconflow.com/v1/chat/completions", "deepseek-ai/DeepSeek-V3"),
]


# --------------------------------------------------------------------------- #
# Perfis sonoros (o que realmente viraliza hoje, por nicho)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    bpm: float
    tags: tuple[str, ...]
    root: float          # frequência da tônica do sub-baixo (Hz)
    chords: tuple[tuple[float, ...], ...]
    swing: float = 0.0
    hat_rate: int = 2    # hats por batida
    energy: float = 0.8

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "bpm": self.bpm,
            "tags": list(self.tags),
            "energy": self.energy,
        }


def _minor(root: float) -> tuple[tuple[float, ...], ...]:
    """i – VI – III – VII (a progressão de praticamente todo corte viral)."""
    r = root
    return (
        (r, r * 1.1892, r * 1.4983),        # i
        (r * 0.7937, r * 1.0, r * 1.2599),  # VI
        (r * 0.5946, r * 0.7492, r * 0.8909),  # III
        (r * 0.8909, r * 1.1225, r * 1.3348),  # VII
    )


PROFILES: dict[str, Profile] = {
    "phonk": Profile(
        "phonk", "Phonk agressivo (sub pesado, cowbell)", 138.0,
        ("phonk", "drift", "agressivo", "gym", "dark"), 55.0, _minor(220.0),
        hat_rate=4, energy=1.0,
    ),
    "drill": Profile(
        "drill", "Drill / trap sombrio", 142.0,
        ("drill", "trap", "sombrio", "urbano", "hype"), 49.0, _minor(196.0),
        swing=0.12, hat_rate=3, energy=0.95,
    ),
    "epic": Profile(
        "epic", "Épico híbrido (trailer / superação)", 120.0,
        ("epico", "cinematico", "motivacao", "trailer", "orquestral"), 65.0, _minor(261.6),
        hat_rate=1, energy=0.9,
    ),
    "lofi": Profile(
        "lofi", "Lo-fi calmo (storytelling / podcast)", 84.0,
        ("lofi", "calmo", "storytelling", "podcast", "chill"), 73.4, _minor(174.6),
        swing=0.18, hat_rate=2, energy=0.5,
    ),
    "corporate": Profile(
        "corporate", "Corporativo limpo (negócios / dados)", 108.0,
        ("corporativo", "limpo", "negocios", "tech", "moderno"), 82.4, _minor(261.6),
        hat_rate=2, energy=0.65,
    ),
    "pop": Profile(
        "pop", "Pop dançante (lifestyle / humor)", 124.0,
        ("pop", "dance", "alegre", "lifestyle", "humor"), 87.3, _minor(293.7),
        hat_rate=2, energy=0.85,
    ),
    "suspense": Profile(
        "suspense", "Suspense / true crime", 96.0,
        ("suspense", "misterio", "tenso", "crime", "dark"), 61.7, _minor(196.0),
        hat_rate=1, energy=0.7,
    ),
}

# Nicho da Fábrica de Cortes → perfil padrão (usado quando não há IA disponível).
NICHE_PROFILE: dict[str, str] = {
    "auto": "epic",
    "motivacao": "epic",
    "negocios": "corporate",
    "podcast": "lofi",
    "educacao": "corporate",
    "saude": "phonk",
    "fitness": "phonk",
    "tecnologia": "corporate",
    "humor": "pop",
    "relacionamento": "lofi",
    "crime": "suspense",
    "misterio": "suspense",
    "espiritual": "epic",
    "games": "drill",
    "esporte": "phonk",
    "financas": "corporate",
    "noticias": "suspense",
}

# Palavras da própria transcrição que puxam o perfil (2ª camada, sem IA).
KEYWORD_PROFILE: list[tuple[str, tuple[str, ...]]] = [
    ("phonk", ("treino", "academia", "musculo", "shape", "disciplina brutal", "monstro")),
    ("drill", ("rua", "quebrada", "game", "gameplay", "rap", "trap")),
    ("epic", ("sonho", "superacao", "vencer", "proposito", "impossivel", "historia de vida")),
    ("lofi", ("conversa", "entrevista", "reflexao", "calma", "estudo", "leitura")),
    ("corporate", ("faturamento", "empresa", "investimento", "planilha", "mercado", "estrategia")),
    ("pop", ("engracado", "risada", "meme", "trend", "danca", "namorada")),
    ("suspense", ("crime", "assassino", "policia", "desaparecid", "misterio", "investigacao")),
]


def profile_for(niche_id: str, transcript: str = "") -> Profile:
    """Perfil determinístico: nicho + pistas do texto. Nunca falha."""
    flat = _fold(transcript)[:20_000]
    scores: dict[str, float] = {pid: 0.0 for pid in PROFILES}
    base = NICHE_PROFILE.get(niche_id, "epic")
    scores[base] += 2.0
    for pid, words in KEYWORD_PROFILE:
        hits = sum(flat.count(w) for w in words)
        if hits:
            scores[pid] += min(3.0, hits * 0.5)
    best = max(scores.items(), key=lambda kv: kv[1])[0]
    return PROFILES[best]


# --------------------------------------------------------------------------- #
# Biblioteca do servidor
# --------------------------------------------------------------------------- #
@dataclass
class Track:
    id: str
    label: str
    path: Path
    origin: str                     # library | upload | synth
    bpm: float = 0.0
    duration: float = 0.0
    tags: list[str] = field(default_factory=list)
    profile: str | None = None
    reason: str = ""
    beats: list[float] = field(default_factory=list)
    offset: float = 0.0             # 1º ataque forte (onde a trilha deve começar)
    confidence: float = 0.0

    @property
    def grid_bpm(self) -> float:
        """BPM normalizado para 90–180 — evita grade em meio-tempo (68 → 136)."""
        bpm = self.bpm
        if bpm <= 0:
            return 0.0
        while bpm < 90:
            bpm *= 2
        while bpm > 180:
            bpm /= 2
        return round(bpm, 2)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "origin": self.origin,
            "grid_bpm": self.grid_bpm,
            "bpm": round(self.bpm, 2),
            "duration": round(self.duration, 2),
            "tags": self.tags,
            "profile": self.profile,
            "reason": self.reason,
            "offset": round(self.offset, 3),
            "confidence": round(self.confidence, 3),
            "filename": self.path.name,
        }


def library_dir() -> Path:
    path = config.storage_dir / "trilhas"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_file() -> Path:
    return library_dir() / "_index.json"


def _fold(text: str) -> str:
    import unicodedata

    norm = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in norm if not unicodedata.combining(ch))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _fold(name)).strip("-") or "faixa"


def _tags_from_name(name: str) -> list[str]:
    """`phonk_140bpm_gym.mp3` → ['phonk', 'gym'] (o BPM vira metadado)."""
    parts = [p for p in re.split(r"[^a-z0-9]+", _fold(name)) if p and not p.endswith("bpm")]
    return [p for p in parts if len(p) > 2 and not p.isdigit()][:8]


def _analyze(path: Path) -> dict[str, Any]:
    from .sterilizer import probe_duration

    duration = float(probe_duration(path) or 0.0)
    beat_map = beatsync.detect_beats(path, duration=min(duration, 120.0))
    onset = beat_map.onsets[0] if beat_map.onsets else 0.0
    return {
        "bpm": beat_map.bpm,
        "duration": duration,
        "confidence": beat_map.confidence,
        "offset": round(min(onset, 4.0), 3),
    }


def library(refresh: bool = False) -> list[Track]:
    """Faixas do servidor com BPM medido (cache em `trilhas/_index.json`)."""
    folder = library_dir()
    cache: dict[str, Any] = {}
    cache_path = _cache_file()
    if cache_path.exists() and not refresh:
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache = {}

    tracks: list[Track] = []
    dirty = False
    for file in sorted(folder.iterdir()):
        if not file.is_file() or file.suffix.lower() not in AUDIO_SUFFIX:
            continue
        stat = file.stat()
        key = f"{file.name}:{stat.st_size}:{int(stat.st_mtime)}"
        meta = cache.get(key)
        if not isinstance(meta, dict):
            meta = _analyze(file)
            cache = {k: v for k, v in cache.items() if not k.startswith(f"{file.name}:")}
            cache[key] = meta
            dirty = True
        tracks.append(
            Track(
                id=_slug(file.stem),
                label=file.stem.replace("_", " ").strip(),
                path=file,
                origin="library",
                bpm=float(meta.get("bpm") or 0.0),
                duration=float(meta.get("duration") or 0.0),
                tags=_tags_from_name(file.stem),
                offset=float(meta.get("offset") or 0.0),
                confidence=float(meta.get("confidence") or 0.0),
            )
        )

    if dirty:
        try:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass
    return tracks


def find(track_id: str) -> Track | None:
    for track in library():
        if track.id == track_id:
            return track
    return None


# --------------------------------------------------------------------------- #
# Síntese (fallback sempre disponível, 100% original)
# --------------------------------------------------------------------------- #
def _kick(bpm: float, gain: float) -> str:
    beat = 60.0 / bpm
    # envelope exponencial por batida + pitch drop (55 Hz → 42 Hz)
    return (
        f"aevalsrc='{gain:.2f}*sin(2*PI*(48+34*exp(-24*mod(t\\,{beat:.5f})))*t)"
        f"*exp(-11*mod(t\\,{beat:.5f}))':s=44100:d=DUR"
    )


def _sub(bpm: float, root: float, gain: float) -> str:
    bar = 60.0 / bpm * 4
    # tônica na 1ª metade do compasso, quinta na 2ª
    return (
        f"aevalsrc='{gain:.2f}*sin(2*PI*({root:.2f}+{root * 0.5:.2f}"
        f"*gt(mod(t\\,{bar:.5f})\\,{bar / 2:.5f}))*t)"
        f"*(0.55+0.45*sin(2*PI*t*{bpm / 60:.4f}))':s=44100:d=DUR"
    )


def _hats(bpm: float, rate: int, gain: float, swing: float) -> str:
    step = 60.0 / bpm / max(1, rate)
    sw = 1.0 + swing * 0.35
    return (
        f"aevalsrc='{gain:.2f}*(random(0)-0.5)"
        f"*exp(-90*mod(t*{sw:.4f}\\,{step:.5f}))':s=44100:d=DUR"
    )


def _pad(bpm: float, chords: tuple[tuple[float, ...], ...], gain: float) -> str:
    bar = 60.0 / bpm * 4
    cycle = bar * len(chords)
    terms: list[str] = []
    for index, chord in enumerate(chords):
        window = (
            f"between(mod(t\\,{cycle:.5f})\\,{index * bar:.5f}\\,{(index + 1) * bar:.5f})"
        )
        voices = "+".join(f"sin(2*PI*{freq:.2f}*t)" for freq in chord)
        terms.append(f"({window})*({voices})")
    body = "+".join(terms)
    return f"aevalsrc='{gain:.3f}*({body})*(0.7+0.3*sin(2*PI*t*0.13))':s=44100:d=DUR"


def synthesize(profile: Profile, seconds: float, dst: Path, *, job_id: str | None = None) -> Track:
    """Gera uma trilha original no perfil escolhido (kick+sub+hats+pad)."""
    from . import media

    seconds = max(6.0, min(seconds + 2.0, 900.0))
    dur = f"{seconds:.2f}"
    energy = profile.energy
    sources = [
        _kick(profile.bpm, 0.95 * energy),
        _sub(profile.bpm, profile.root, 0.42 * energy),
        _hats(profile.bpm, profile.hat_rate, 0.16 * energy, profile.swing),
        _pad(profile.bpm, profile.chords, 0.055 + 0.03 * (1 - energy)),
    ]
    inputs: list[str] = []
    for src in sources:
        inputs += ["-f", "lavfi", "-i", src.replace("DUR", dur)]

    dst.parent.mkdir(parents=True, exist_ok=True)
    media.run(
        [
            config.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
            *inputs,
            "-filter_complex",
            "[0:a]highpass=f=28,lowpass=f=180[k];"
            "[1:a]lowpass=f=140[b];"
            "[2:a]highpass=f=6500[h];"
            "[3:a]lowpass=f=2600,aformat=channel_layouts=mono[p];"
            "[k][b][h][p]amix=inputs=4:normalize=0[mix];"
            "[mix]acompressor=threshold=0.15:ratio=4:attack=8:release=180,"
            "alimiter=limit=0.94,loudnorm=I=-15:TP=-1.5:LRA=9,"
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a]",
            "-map", "[a]", "-c:a", "aac", "-b:a", "192k", str(dst),
        ],
        job_id=job_id,
    )
    return Track(
        id=f"synth-{profile.id}",
        label=f"Trilha original · {profile.label}",
        path=dst,
        origin="synth",
        bpm=profile.bpm,
        duration=seconds,
        tags=list(profile.tags),
        profile=profile.id,
        reason=f"Trilha gerada no perfil {profile.label} — original, sem Content ID.",
        beats=beatsync.beats_from_bpm(profile.bpm, seconds),
        offset=0.0,
        confidence=1.0,
    )


# --------------------------------------------------------------------------- #
# Escolha inteligente
# --------------------------------------------------------------------------- #
def _match(track: Track, profile: Profile) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    hits = [tag for tag in profile.tags if any(tag in t or t in tag for t in track.tags)]
    if hits:
        score += min(4.0, len(hits) * 1.4)
        reasons.append(f"tags {', '.join(hits[:3])}")
    if track.bpm > 0:
        diff = abs(track.bpm - profile.bpm)
        diff = min(diff, abs(track.bpm * 2 - profile.bpm), abs(track.bpm / 2 - profile.bpm))
        if diff <= 6:
            score += 3.0
            reasons.append(f"BPM {track.bpm:.0f} casa com o perfil")
        elif diff <= 14:
            score += 1.6
            reasons.append(f"BPM {track.bpm:.0f} próximo do perfil")
        score += track.confidence
    if track.duration >= 25:
        score += 0.6
    return score, reasons


def _llm_profile(niche_id: str, transcript: str, timeout: int = 40) -> tuple[str | None, str, str | None]:
    """IA decide o perfil sonoro viral. Falhou? Devolve (None, '', None)."""
    if not any(api_keys.get_key(pid) for pid, _u, _m in _ROUTES):
        return None, "", None
    from .trends import _http_json

    catalog = [{"id": p.id, "estilo": p.label, "bpm": p.bpm} for p in PROFILES.values()]
    system = (
        "Você é diretor musical de cortes virais (TikTok/Reels/Shorts) e acompanha "
        "as trilhas que estão performando AGORA.\n"
        "Escolha o PERFIL SONORO livre de direitos autorais que mais aumenta retenção "
        "para o conteúdo abaixo. Nunca cite música comercial, artista ou faixa protegida.\n"
        'Responda SOMENTE JSON: {"perfil":"<id>","motivo":"até 110 caracteres"}'
    )
    user = json.dumps(
        {
            "nicho": niche_id,
            "perfis_disponiveis": catalog,
            "trecho_do_video": transcript[:2500],
        },
        ensure_ascii=False,
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
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
            content = data["choices"][0]["message"]["content"]
            start, end = content.find("{"), content.rfind("}")
            if start == -1:
                continue
            parsed = json.loads(content[start : end + 1])
            pid = str(parsed.get("perfil") or "").strip()
            if pid in PROFILES:
                return pid, str(parsed.get("motivo") or "").strip()[:140], provider
        except Exception:  # noqa: BLE001 - qualquer falha cai na heurística
            continue
    return None, "", None


def pick(
    *,
    niche_id: str,
    transcript: str = "",
    seconds: float = 60.0,
    workdir: Path | None = None,
    use_ai: bool = True,
    job_id: str | None = None,
) -> Track:
    """Modo automático: perfil por IA (ou heurística) → melhor faixa → síntese."""
    profile = profile_for(niche_id, transcript)
    reason_prefix = f"Perfil {profile.label} pelo nicho e pelo texto do vídeo."
    provider = None
    if use_ai:
        pid, motive, provider = _llm_profile(niche_id, transcript)
        if pid:
            profile = PROFILES[pid]
            reason_prefix = motive or f"IA escolheu o perfil {profile.label}."

    best: tuple[float, Track, list[str]] | None = None
    for track in library():
        score, reasons = _match(track, profile)
        if best is None or score > best[0]:
            best = (score, track, reasons)

    if best and best[0] >= 3.0:
        score, track, reasons = best
        track.profile = profile.id
        track.reason = " ".join(
            filter(None, [reason_prefix, ("Faixa da biblioteca: " + "; ".join(reasons)) if reasons else ""])
        )
        if provider:
            track.reason += f" (IA via {provider})"
        return prepare(track)

    folder = workdir or (config.storage_dir / "trilhas" / "_synth")
    seed = hashlib.md5(f"{profile.id}:{niche_id}:{int(seconds)}".encode()).hexdigest()[:8]
    dst = folder / f"trilha_{profile.id}_{seed}.m4a"
    if not dst.exists():
        random.seed(seed)
        synthesize(profile, seconds, dst, job_id=job_id)
    track = Track(
        id=f"synth-{profile.id}",
        label=f"Trilha original · {profile.label}",
        path=dst,
        origin="synth",
        bpm=profile.bpm,
        duration=seconds,
        tags=list(profile.tags),
        profile=profile.id,
        beats=beatsync.beats_from_bpm(profile.bpm, seconds),
        confidence=1.0,
        reason=(
            f"{reason_prefix} Biblioteca sem faixa compatível — trilha sintetizada "
            f"a {profile.bpm:.0f} BPM, original e sem Content ID."
            + (f" (IA via {provider})" if provider else "")
        ),
    )
    return track


def prepare(track: Track) -> Track:
    """Garante BPM/beats medidos na faixa (upload ou biblioteca)."""
    if track.beats:
        return track
    beat_map = beatsync.detect_beats(track.path, duration=min(track.duration or 90.0, 120.0))
    track.bpm = track.bpm or beat_map.bpm
    track.confidence = max(track.confidence, beat_map.confidence)
    if beat_map.onsets and not track.offset:
        track.offset = round(min(beat_map.onsets[0], 4.0), 3)
    track.beats = beat_map.beats or beatsync.beats_from_bpm(track.bpm, track.duration or 90.0)
    return track


def resolve(
    *,
    mode: str,
    upload: Path | None,
    track_id: str | None,
    niche_id: str,
    transcript: str,
    seconds: float,
    workdir: Path | None,
    use_ai: bool,
    job_id: str | None = None,
) -> Track | None:
    """Ponte usada pelo clipper: devolve a faixa final já analisada."""
    mode = mode if mode in MODES else "none"
    if mode == "none":
        return None
    if mode == "upload":
        if not upload or not upload.exists():
            return None
        from .sterilizer import probe_duration

        return prepare(
            Track(
                id="upload",
                label=upload.stem.replace("_", " "),
                path=upload,
                origin="upload",
                duration=float(probe_duration(upload) or 0.0),
                tags=_tags_from_name(upload.stem),
                reason="Áudio enviado pelo operador.",
            )
        )
    if mode == "library":
        track = find(track_id or "")
        if not track:
            return None
        track.reason = "Faixa escolhida na biblioteca do servidor."
        return prepare(track)
    return pick(
        niche_id=niche_id,
        transcript=transcript,
        seconds=seconds,
        workdir=workdir,
        use_ai=use_ai,
        job_id=job_id,
        force_synth=mode == "synth",
    )



def bars_duration(
    seconds: float, bpm: float, *, beats_per_bar: int = 4, ceiling: float | None = None
) -> float:
    """Encaixa a duração no compasso mais próximo (encurta ou estica um pouco).

    `ceiling` é o limite que o corte não pode ultrapassar (fim do vídeo ou
    duração máxima pedida). Sem espaço para esticar, encurta.
    """
    if bpm <= 0:
        return seconds
    bar = 60.0 / bpm * beats_per_bar
    if bar <= 0 or seconds < bar:
        return seconds
    low = math.floor(seconds / bar) * bar
    high = low + bar
    if ceiling is not None and high > ceiling:
        return round(low, 3)
    best = high if (high - seconds) <= (seconds - low) else low
    return round(best, 3)


def catalog() -> dict[str, Any]:
    return {
        "modes": list(MODES),
        "profiles": [p.as_dict() for p in PROFILES.values()],
        "tracks": [t.as_dict() for t in library()],
        "library_dir": str(library_dir()),
        "ai_ready": any(api_keys.get_key(pid) for pid, _u, _m in _ROUTES),
    }
