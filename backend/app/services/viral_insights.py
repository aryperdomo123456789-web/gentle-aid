"""Detecção determinística de oportunidades de cortes a partir de json_verbose.

O score é uma heurística de priorização, não uma previsão de viralização. Ele é
explicável e retorna os sinais que contribuíram para cada janela.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .transcription_exports import normalized_segments

MIN_WINDOW_SECONDS = 30.0
MAX_WINDOW_SECONDS = 90.0
WINDOW_STEP_SECONDS = 15.0

_HOOK_PATTERNS = (
    r"\b(?:a verdade|ningu[eé]m te conta|o que eu descobri|o maior erro|pare de|n[aã]o fa[cç]a|como eu|por que|porqu[eê]|você sabia|voc[eê] sabia)\b",
    r"\b(?:segredo|inacredit[aá]vel|surpreendente|aten[cç][aã]o|importante|cuidado|nunca|jamais)\b",
    r"\b(?:em [0-9]+|[0-9]+%|R\$\s*[0-9]+|[0-9]+x)\b",
)
_CLIMAX_PATTERNS = (
    r"\b(?:mas|por[eé]m|at[eé] que|s[oó] que|ent[aã]o|por isso|resultado|no fim|descobri|funcionou)\b",
    r"\b(?:prova|resultado|ganhei|perdi|economizei|aumentou|dobrou|triplicou|mudou)\b",
)
_PROOF_PATTERNS = (
    r"\b(?:n[uú]mero|dados|teste|prova|resultado|cliente|vendas|faturamento|dias|passos|exemplo)\b",
    r"(?:\b[0-9]+(?:[.,][0-9]+)?%|\bR\$\s*[0-9]+|\b[0-9]+x)\b",
)
_QUESTION_PATTERN = re.compile(r"\?")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class InsightWindow:
    start: float
    end: float
    text: str
    score: int
    title: str
    hook: str
    summary: str
    signals: dict[str, float]
    reasons: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration_seconds": round(max(0.0, self.end - self.start), 3),
            "retention_score": int(self.score),
            "suggested_title": self.title,
            "initial_hook": self.hook,
            "summary": self.summary,
            "signals": {key: round(value, 3) for key, value in self.signals.items()},
            "reasons": list(self.reasons),
        }


def _text_for(segment: Mapping[str, Any]) -> str:
    return str(segment.get("text") or "").strip()


def _matches(patterns: Iterable[str], text: str) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, re.IGNORECASE))


def _clip_text(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rsplit(" ", 1)[0] + "…"


def _window_segments(segments: list[dict[str, Any]], start: float, end: float) -> list[dict[str, Any]]:
    return [
        segment
        for segment in segments
        if float(segment.get("end", 0.0)) > start and float(segment.get("start", 0.0)) < end
    ]


def _candidate_starts(segments: list[dict[str, Any]], duration: float) -> list[float]:
    if duration <= MAX_WINDOW_SECONDS:
        return [0.0]
    starts = {0.0}
    cursor = 0.0
    while cursor + MIN_WINDOW_SECONDS <= duration:
        starts.add(round(cursor, 3))
        cursor += WINDOW_STEP_SECONDS
    for segment in segments:
        start = float(segment.get("start", 0.0))
        if 0.0 <= start <= max(0.0, duration - MIN_WINDOW_SECONDS):
            starts.add(round(start, 3))
    return sorted(starts)


def _score_window(window_segments: list[dict[str, Any]], start: float, end: float) -> InsightWindow:
    text = " ".join(_text_for(segment) for segment in window_segments).strip()
    window_duration = max(1.0, end - start)
    words = re.findall(r"\b[\wÀ-ÿ']+\b", text)
    word_count = len(words)
    density = min(1.0, word_count / (window_duration * 2.1))
    first_text = " ".join(_text_for(segment) for segment in window_segments[:3])
    hook_hits = _matches(_HOOK_PATTERNS, first_text)
    climax_hits = _matches(_CLIMAX_PATTERNS, text)
    proof_hits = _matches(_PROOF_PATTERNS, text)
    questions = len(_QUESTION_PATTERN.findall(text))
    hook_strength = min(1.0, hook_hits / 2.0 + min(0.25, questions * 0.12))
    climax_strength = min(1.0, climax_hits / 3.0)
    proof_strength = min(1.0, proof_hits / 2.0)
    coverage = min(1.0, len(window_segments) / max(2.0, window_duration / 15.0))
    narrative = min(1.0, 0.45 * coverage + 0.55 * (1.0 if text else 0.0))
    raw_score = 100 * (
        0.30 * density
        + 0.25 * hook_strength
        + 0.20 * climax_strength
        + 0.15 * proof_strength
        + 0.10 * narrative
    )
    reasons: list[str] = []
    if density >= 0.65:
        reasons.append("alta densidade verbal")
    if hook_strength >= 0.35:
        reasons.append("gancho forte no início")
    if climax_strength >= 0.34:
        reasons.append("virada ou clímax detectado")
    if proof_strength >= 0.5:
        reasons.append("prova, número ou resultado específico")
    if questions:
        reasons.append("pergunta que abre curiosidade")
    if not reasons:
        reasons.append("contexto contínuo suficiente para teste")
    title_source = first_text or text or "Corte sugerido"
    title = _clip_text(title_source.split(".", 1)[0], 72)
    if not title:
        title = "Corte sugerido"
    hook = _clip_text(first_text or text, 160)
    summary = _clip_text(text, 280)
    return InsightWindow(
        start=start,
        end=end,
        text=text,
        score=max(0, min(100, round(raw_score))),
        title=title,
        hook=hook,
        summary=summary,
        signals={
            "context_density": density,
            "hook_strength": hook_strength,
            "climax_strength": climax_strength,
            "proof_strength": proof_strength,
            "narrative_coverage": narrative,
        },
        reasons=reasons,
    )


def _overlap_ratio(left: InsightWindow, right: InsightWindow) -> float:
    overlap = max(0.0, min(left.end, right.end) - max(left.start, right.start))
    shorter = max(0.1, min(left.end - left.start, right.end - right.start))
    return overlap / shorter


def detect_viral_clips(payload: Mapping[str, Any], *, max_clips: int = 5) -> list[dict[str, Any]]:
    """Retorna oportunidades ordenadas por score, sem alegar certeza de alcance."""
    segments = normalized_segments(payload.get("segments") or [])
    if not segments:
        return []
    declared_duration = payload.get("duration_seconds")
    try:
        duration = float(declared_duration)
    except (TypeError, ValueError):
        duration = max(float(segment.get("end", 0.0)) for segment in segments)
    duration = max(duration, max(float(segment.get("end", 0.0)) for segment in segments))
    candidates: list[InsightWindow] = []
    for start in _candidate_starts(segments, duration):
        end = min(duration, start + MAX_WINDOW_SECONDS)
        if end - start < MIN_WINDOW_SECONDS:
            continue
        selected = _window_segments(segments, start, end)
        if selected:
            candidates.append(_score_window(selected, start, end))
    candidates.sort(key=lambda item: (-item.score, item.start))
    chosen: list[InsightWindow] = []
    for candidate in candidates:
        if any(_overlap_ratio(candidate, item) > 0.65 for item in chosen):
            continue
        chosen.append(candidate)
        if len(chosen) >= max(1, min(20, int(max_clips))):
            break
    return [item.as_dict() for item in chosen]


def analyze_json_verbose(payload: Mapping[str, Any], *, max_clips: int = 5) -> dict[str, Any]:
    """Envelopa insights com versão do heurístico para auditoria e evolução futura."""
    clips = detect_viral_clips(payload, max_clips=max_clips)
    duration = payload.get("duration_seconds")
    return {
        "object": "viral_insights",
        "engine": "heuristic-v1",
        "disclaimer": "Score estimado para priorização editorial; não garante viralização.",
        "duration_seconds": duration,
        "clips": clips,
        "count": len(clips),
    }
