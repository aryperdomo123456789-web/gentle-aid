"""Fonte visual das cenas do gerador de vídeo.

Quatro modos, todos plugáveis na mesma interface `fetch(scene, ...) -> Asset`:

* `ia`      — imagem gerada de graça pela Pollinations (sem chave, ilimitada);
* `broll`   — vídeo real de banco gratuito (Pexels → Pixabay, chave grátis);
* `upload`  — mídia enviada pelo operador, distribuída pelas cenas na ordem;
* `premium` — slot para vídeo por IA pago (Runway/Kling/Veo) via Central de APIs.

Nenhum modo derruba o job: quando a fonte escolhida falha, cai para a próxima
opção disponível e, no pior caso, para um cartão de cor sólida gerado local-
mente pelo FFmpeg. O motivo real fica registrado no rastro do job.
"""

from __future__ import annotations

import json
import random
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import api_keys, jobs

MODES = ("ia", "broll", "upload", "premium")

POLLINATIONS = "https://image.pollinations.ai/prompt/"
_UA = "EcossistemaViral/1.0 (+aaPanel)"
_TIMEOUT = 90


@dataclass
class Asset:
    """Mídia bruta de uma cena antes de virar clipe."""

    path: Path
    kind: str  # "image" | "video" | "color"
    source: str  # pollinations | pexels | pixabay | upload | fallback


class VisualError(RuntimeError):
    """Nenhuma fonte visual conseguiu entregar mídia para a cena."""


def _download(url: str, dst: Path, *, headers: dict[str, str] | None = None) -> Path:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", _UA)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as res:  # noqa: S310
        dst.write_bytes(res.read())
    if not dst.exists() or dst.stat().st_size < 1024:
        dst.unlink(missing_ok=True)
        raise VisualError(f"Download vazio: {url[:120]}")
    return dst


def _json(url: str, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", _UA)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as res:  # noqa: S310
        return json.loads(res.read().decode("utf-8", "replace"))


# --------------------------------------------------------------------------- #
# Fontes
# --------------------------------------------------------------------------- #
def pollinations(prompt: str, dst: Path, *, width: int, height: int, seed: int) -> Asset:
    """Imagem por IA sem chave e sem limite prático — base do estilo 'canal viral'."""
    query = urllib.parse.urlencode(
        {"width": width, "height": height, "seed": seed, "nologo": "true", "model": "flux"}
    )
    url = f"{POLLINATIONS}{urllib.parse.quote(prompt[:900])}?{query}"
    _download(url, dst)
    return Asset(path=dst, kind="image", source="pollinations")


def pexels_video(query: str, dst: Path, *, portrait: bool) -> Asset:
    key = api_keys.get_key("pexels")
    if not key:
        raise VisualError("Sem chave Pexels.")
    params = urllib.parse.urlencode(
        {
            "query": query or "abstract background",
            "per_page": 8,
            "orientation": "portrait" if portrait else "landscape",
        }
    )
    data = _json(f"https://api.pexels.com/videos/search?{params}", {"Authorization": key})
    for video in data.get("videos") or []:
        files = sorted(
            (f for f in video.get("video_files") or [] if f.get("link")),
            key=lambda f: abs((f.get("height") or 0) - (1920 if portrait else 1080)),
        )
        if files:
            _download(files[0]["link"], dst)
            return Asset(path=dst, kind="video", source="pexels")
    raise VisualError(f"Pexels não achou b-roll para '{query}'.")


def pixabay_video(query: str, dst: Path) -> Asset:
    key = api_keys.get_key("pixabay")
    if not key:
        raise VisualError("Sem chave Pixabay.")
    params = urllib.parse.urlencode({"key": key, "q": query or "background", "per_page": 10})
    data = _json(f"https://pixabay.com/api/videos/?{params}")
    for hit in data.get("hits") or []:
        videos = hit.get("videos") or {}
        for size in ("large", "medium", "small"):
            link = (videos.get(size) or {}).get("url")
            if link:
                _download(link, dst)
                return Asset(path=dst, kind="video", source="pixabay")
    raise VisualError(f"Pixabay não achou b-roll para '{query}'.")


def premium_video(_query: str, _dst: Path) -> Asset:
    """Slot reservado para vídeo por IA pago (Runway/Kling/Veo)."""
    raise VisualError(
        "Modo 'Vídeo IA pago' ainda não tem provedor conectado. Cadastre a chave em /apis "
        "ou use os modos gratuitos (imagem IA / b-roll)."
    )


# --------------------------------------------------------------------------- #
# Seleção por cena
# --------------------------------------------------------------------------- #
def fetch(
    scene: dict,
    *,
    mode: str,
    workdir: Path,
    index: int,
    width: int,
    height: int,
    look_suffix: str,
    uploads: list[Path],
    job_id: str,
    seed: int,
) -> Asset:
    workdir.mkdir(parents=True, exist_ok=True)
    portrait = height >= width
    prompt = f"{scene.get('visual') or scene.get('narration', '')}. {look_suffix}".strip()
    query = scene.get("query") or " ".join(str(scene.get("visual", "")).split()[:4])

    order: list[str] = []
    if mode == "upload" and uploads:
        order = ["upload", "ia", "broll"]
    elif mode == "broll":
        order = ["broll", "ia"]
    elif mode == "premium":
        order = ["premium", "broll", "ia"]
    else:
        order = ["ia", "broll"]

    errors: list[str] = []
    for source in order:
        try:
            if source == "upload":
                picked = uploads[index % len(uploads)]
                return Asset(path=picked, kind=_kind_of(picked), source="upload")
            if source == "ia":
                dst = workdir / f"scene_{index:03d}.jpg"
                return pollinations(prompt, dst, width=width, height=height, seed=seed + index)
            if source == "broll":
                dst = workdir / f"scene_{index:03d}.mp4"
                try:
                    return pexels_video(query, dst, portrait=portrait)
                except Exception as exc:  # noqa: BLE001 — tenta o segundo banco
                    errors.append(f"pexels: {exc}")
                    return pixabay_video(query, dst)
            if source == "premium":
                return premium_video(query, workdir / f"scene_{index:03d}.mp4")
        except Exception as exc:  # noqa: BLE001 — fonte fora do ar: tenta a próxima
            errors.append(f"{source}: {exc}")
            jobs.log(
                job_id,
                f"Cena {index + 1}: fonte '{source}' falhou ({str(exc)[:120]}) — tentando a próxima.",
                level="warn",
                stage="visual",
            )

    raise VisualError(" · ".join(errors[-3:]) or "Nenhuma fonte visual disponível.")


def _kind_of(path: Path) -> str:
    return "video" if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"} else "image"


def solid_card(dst: Path, *, width: int, height: int, ffmpeg: str, runner) -> Asset:
    """Último recurso: cartão de cor sólida para o vídeo nunca quebrar no meio."""
    color = random.choice(["#101828", "#1d1b3a", "#232323", "#0f2027"]).replace("#", "0x")
    runner(
        [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:d=1",
            "-frames:v", "1", str(dst),
        ],
        job_id=None,
    )
    return Asset(path=dst, kind="image", source="fallback")
