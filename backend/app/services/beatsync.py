"""Beat sync — detecta o ritmo da música do vídeo e encaixa a legenda nele.

Roda 100% no servidor (aaPanel) com o FFmpeg que já está instalado. Não usa
numpy, librosa ou qualquer dependência extra: o áudio é decodificado para PCM
mono 11 kHz e a análise é feita com `array` puro, o que é rápido o bastante
(um vídeo de 60 s vira ~660 mil amostras / ~1.300 quadros de análise).

Pipeline:

    ffmpeg -vn -ac 1 -ar 11025 -f s16le  ──▶  envelope de energia (hop 512)
                                          ──▶  fluxo positivo (onset strength)
                                          ──▶  pico com limiar adaptativo
                                          ──▶  BPM por histograma de intervalos
                                          ──▶  grade regular de batidas
                                          ──▶  snap das palavras/linhas

O snap nunca inverte a ordem das palavras nem cria evento negativo: se a batida
mais próxima estiver longe demais (`tolerance`), a palavra fica onde estava.
"""

from __future__ import annotations

import array
import subprocess
from dataclasses import dataclass
from typing import Iterable, Sequence

from .captions import Line, Word

__all__ = ["BeatMap", "detect_beats", "snap_lines", "snap_words", "beats_from_bpm"]

SAMPLE_RATE = 11025
HOP = 512  # ~46,4 ms por quadro
MIN_BPM = 60.0
MAX_BPM = 190.0


@dataclass
class BeatMap:
    bpm: float
    beats: list[float]
    onsets: list[float]
    confidence: float
    source: str = "audio"

    @property
    def ok(self) -> bool:
        return len(self.beats) >= 4


# --------------------------------------------------------------------------- #
# Decodificação
# --------------------------------------------------------------------------- #
def _decode_pcm(path, *, max_seconds: float = 600.0) -> array.array:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-t", f"{max_seconds:.2f}",
        "-i", str(path),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    raw = proc.stdout or b""
    if len(raw) < 4:
        return array.array("h")
    if len(raw) % 2:
        raw = raw[:-1]
    samples = array.array("h")
    samples.frombytes(raw)
    return samples


def _energy_envelope(samples: Sequence[int]) -> list[float]:
    env: list[float] = []
    total = len(samples)
    for start in range(0, total - HOP + 1, HOP):
        acc = 0
        for i in range(start, start + HOP, 4):  # subamostra: 4x mais rápido, mesma curva
            v = samples[i]
            acc += v * v
        env.append((acc / (HOP / 4)) ** 0.5)
    return env


def _onset_strength(env: Sequence[float]) -> list[float]:
    """Fluxo positivo em escala log — realça ataques de bumbo/caixa."""
    out = [0.0]
    for i in range(1, len(env)):
        prev = env[i - 1] + 1e-6
        cur = env[i] + 1e-6
        import math

        out.append(max(0.0, math.log(cur) - math.log(prev)))
    return out


def _pick_peaks(flux: Sequence[float], *, min_gap_frames: int = 3) -> list[int]:
    if not flux:
        return []
    window = 21
    peaks: list[int] = []
    last = -10_000
    for i in range(1, len(flux) - 1):
        lo = max(0, i - window)
        hi = min(len(flux), i + window + 1)
        local = flux[lo:hi]
        mean = sum(local) / len(local)
        # desvio médio absoluto (mais barato e estável que desvio padrão aqui)
        mad = sum(abs(v - mean) for v in local) / len(local)
        threshold = mean + 1.4 * mad
        if flux[i] > threshold and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1]:
            if i - last >= min_gap_frames:
                peaks.append(i)
                last = i
    return peaks


def _estimate_bpm(onsets: Sequence[float]) -> tuple[float, float]:
    """BPM por histograma de intervalos entre ataques, dobrado para 60–190."""
    if len(onsets) < 4:
        return 0.0, 0.0
    buckets: dict[int, float] = {}
    for i, a in enumerate(onsets):
        for b in onsets[i + 1 : i + 5]:
            gap = b - a
            if gap <= 0.2 or gap > 2.5:
                continue
            bpm = 60.0 / gap
            while bpm < MIN_BPM:
                bpm *= 2
            while bpm > MAX_BPM:
                bpm /= 2
            key = int(round(bpm))
            buckets[key] = buckets.get(key, 0.0) + 1.0
            buckets[key - 1] = buckets.get(key - 1, 0.0) + 0.5
            buckets[key + 1] = buckets.get(key + 1, 0.0) + 0.5
    if not buckets:
        return 0.0, 0.0
    best = max(buckets.items(), key=lambda kv: kv[1])
    total = sum(buckets.values()) or 1.0
    return float(best[0]), min(1.0, best[1] / total * 3.0)


def _phase_align(onsets: Sequence[float], period: float, duration: float) -> float:
    """Escolhe o deslocamento da grade que melhor cobre os ataques reais."""
    if not onsets:
        return 0.0
    steps = 24
    best_offset, best_score = onsets[0] % period, -1.0
    for s in range(steps):
        offset = period * s / steps
        score = 0.0
        for t in onsets:
            dist = abs(((t - offset) % period))
            dist = min(dist, period - dist)
            score += max(0.0, 1.0 - dist / (period / 2))
        if score > best_score:
            best_score, best_offset = score, offset
    _ = duration
    return best_offset


def beats_from_bpm(bpm: float, duration: float, offset: float = 0.0) -> list[float]:
    if bpm <= 0 or duration <= 0:
        return []
    period = 60.0 / bpm
    out: list[float] = []
    t = offset % period
    while t <= duration + 1e-6:
        out.append(round(t, 4))
        t += period
    return out


def detect_beats(path, *, duration: float = 0.0) -> BeatMap:
    """Analisa a trilha do arquivo e devolve o mapa de batidas."""
    samples = _decode_pcm(path)
    if len(samples) < SAMPLE_RATE // 2:
        return BeatMap(bpm=0.0, beats=[], onsets=[], confidence=0.0, source="sem-audio")

    env = _energy_envelope(samples)
    flux = _onset_strength(env)
    frames = _pick_peaks(flux)
    seconds_per_frame = HOP / SAMPLE_RATE
    onsets = [round(f * seconds_per_frame, 4) for f in frames]
    total = duration or len(samples) / SAMPLE_RATE

    bpm, confidence = _estimate_bpm(onsets)
    if bpm <= 0:
        return BeatMap(bpm=0.0, beats=onsets, onsets=onsets, confidence=0.0, source="onsets")

    period = 60.0 / bpm
    offset = _phase_align(onsets, period, total)
    beats = beats_from_bpm(bpm, total, offset)
    return BeatMap(bpm=round(bpm, 2), beats=beats, onsets=onsets, confidence=round(confidence, 3))


# --------------------------------------------------------------------------- #
# Encaixe na grade
# --------------------------------------------------------------------------- #
def _nearest(beats: Sequence[float], value: float) -> float:
    if not beats:
        return value
    lo, hi = 0, len(beats) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if beats[mid] < value:
            lo = mid + 1
        else:
            hi = mid
    best = beats[lo]
    if lo > 0 and abs(beats[lo - 1] - value) <= abs(best - value):
        best = beats[lo - 1]
    return best


def snap_words(
    words: Iterable[Word], beats: Sequence[float], *, tolerance: float = 0.22, min_len: float = 0.08
) -> list[Word]:
    """Puxa o início de cada palavra para a batida mais próxima dentro da tolerância."""
    items = list(words)
    if not items or not beats:
        return items
    out: list[Word] = []
    floor = 0.0
    for index, word in enumerate(items):
        target = _nearest(beats, word.start)
        start = target if abs(target - word.start) <= tolerance else word.start
        start = max(start, floor)
        nxt = items[index + 1].start if index + 1 < len(items) else None
        end = word.end
        if nxt is not None:
            end = min(max(end, start + min_len), max(nxt, start + min_len))
        end = max(end, start + min_len)
        out.append(Word(start=round(start, 4), end=round(end, 4), text=word.text))
        floor = out[-1].start + min_len
    # segunda passada: nenhuma palavra invade a seguinte
    for prev, nxt in zip(out, out[1:]):
        if prev.end > nxt.start:
            prev.end = max(prev.start + min_len, nxt.start)
    return out


def snap_lines(lines: Iterable[Line], beats: Sequence[float], *, tolerance: float = 0.22) -> list[Line]:
    """Aplica o snap mantendo o agrupamento já decidido pelo `group_words`."""
    out: list[Line] = []
    for line in lines:
        words = snap_words(line.words, beats, tolerance=tolerance)
        if not words:
            continue
        out.append(Line(start=words[0].start, end=max(words[-1].end, words[0].start + 0.2), words=words))
    for prev, nxt in zip(out, out[1:]):
        if prev.end > nxt.start:
            prev.end = max(prev.start + 0.2, nxt.start)
    return out
