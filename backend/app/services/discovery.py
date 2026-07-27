"""Fluxo de descoberta unificado (padrão do legado, porém normalizado).

Recebe uma palavra-chave, um `@perfil` ou uma URL direta e devolve cards
prontos para a UI: autor, descrição, views/likes/comentários/shares, duração,
data de publicação, thumbnail e uma URL de player embutido para o operador
**assistir antes de codar**.

Fontes: yt-dlp (TikTok e YouTube). Nenhuma chave obrigatória — se uma fonte
falhar, a outra continua alimentando o grid.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from ..config import config
from . import media
from .trends import _compact  # noqa: PLC2701 — helper interno reaproveitado

TIKTOK_URL_RE = re.compile(r"tiktok\.com", re.I)
YOUTUBE_URL_RE = re.compile(r"(youtube\.com|youtu\.be)", re.I)

PLATFORMS = ("auto", "tiktok", "youtube")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _run_json(args: list[str], timeout: int = 120) -> dict[str, Any] | None:
    try:
        raw = media.run([config.ytdlp_bin, *args], timeout=timeout)
    except Exception:  # noqa: BLE001
        return None
    if "{" not in raw:
        return None
    try:
        return json.loads(raw[raw.index("{"):])
    except Exception:  # noqa: BLE001
        return None


def _duration_label(seconds: int) -> str:
    seconds = max(int(seconds or 0), 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _date_label(entry: dict[str, Any]) -> str:
    ts = entry.get("timestamp") or entry.get("release_timestamp")
    if ts:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%d/%m/%Y")
        except Exception:  # noqa: BLE001
            pass
    upload = str(entry.get("upload_date") or "")
    if len(upload) == 8 and upload.isdigit():
        return f"{upload[6:8]}/{upload[4:6]}/{upload[0:4]}"
    return "—"


def _platform_of(url: str, fallback: str) -> str:
    if TIKTOK_URL_RE.search(url or ""):
        return "tiktok"
    if YOUTUBE_URL_RE.search(url or ""):
        return "youtube"
    return fallback


def _embed_url(platform: str, vid: str, url: str) -> str | None:
    if not vid:
        return None
    if platform == "tiktok":
        return f"https://www.tiktok.com/player/v1/{vid}?music_info=1&description=1"
    if platform == "youtube":
        return f"https://www.youtube.com/embed/{vid}"
    return url or None


def _thumbnail(entry: dict[str, Any]) -> str | None:
    thumb = entry.get("thumbnail")
    if thumb:
        return str(thumb)
    thumbs = entry.get("thumbnails") or []
    if isinstance(thumbs, list) and thumbs:
        last = thumbs[-1]
        if isinstance(last, dict) and last.get("url"):
            return str(last["url"])
    return None


def _normalize(entry: dict[str, Any], fallback_platform: str) -> dict[str, Any] | None:
    vid = str(entry.get("id") or "").strip()
    url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
    if not vid and not url:
        return None

    platform = _platform_of(url, fallback_platform)
    author = (
        entry.get("uploader_id")
        or entry.get("uploader")
        or entry.get("channel")
        or entry.get("creator")
        or "desconhecido"
    )
    nickname = entry.get("uploader") or entry.get("channel") or str(author)
    desc = (entry.get("description") or entry.get("title") or "Sem legenda").strip()

    views = int(entry.get("view_count") or 0)
    likes = int(entry.get("like_count") or 0)
    comments = int(entry.get("comment_count") or 0)
    shares = int(entry.get("repost_count") or 0)
    duration = int(entry.get("duration") or 0)

    if not url and vid:
        url = (
            f"https://www.tiktok.com/@{str(author).lstrip('@')}/video/{vid}"
            if platform == "tiktok"
            else f"https://www.youtube.com/watch?v={vid}"
        )

    return {
        "id": vid or url,
        "platform": platform,
        "url": url,
        "embed_url": _embed_url(platform, vid, url),
        "thumbnail": _thumbnail(entry),
        "author": str(author).lstrip("@"),
        "nickname": nickname,
        "title": entry.get("title") or desc[:80],
        "desc": desc[:600],
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "views_label": _compact(views),
        "likes_label": _compact(likes),
        "comments_label": _compact(comments),
        "shares_label": _compact(shares),
        "duration": duration,
        "duration_label": _duration_label(duration),
        "published_label": _date_label(entry),
        "is_short": bool(duration and duration <= 90),
    }


def _entries(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    if payload.get("entries"):
        return [e for e in payload["entries"] if isinstance(e, dict)]
    return [payload]


# --------------------------------------------------------------------------- #
# coletas
# --------------------------------------------------------------------------- #
def _single_url(url: str) -> list[dict[str, Any]]:
    payload = _run_json(
        ["--no-playlist", "--dump-single-json", "--no-warnings", url], timeout=90
    )
    return _entries(payload)


def _flat(target: str, limit: int, timeout: int = 90) -> list[dict[str, Any]]:
    payload = _run_json(
        [
            "--flat-playlist",
            "--dump-single-json",
            "--no-warnings",
            "--playlist-end",
            str(limit),
            target,
        ],
        timeout=timeout,
    )
    return _entries(payload)


def _tiktok_profile(handle: str, limit: int) -> list[dict[str, Any]]:
    return _flat(f"https://www.tiktok.com/@{handle.lstrip('@')}", limit)


def _tiktok_keyword(keyword: str, limit: int) -> list[dict[str, Any]]:
    tag = re.sub(r"[^0-9a-zA-Z]+", "", keyword)[:40]
    if not tag:
        return []
    return _flat(f"https://www.tiktok.com/tag/{tag}", limit)


def _youtube_keyword(keyword: str, limit: int) -> list[dict[str, Any]]:
    return _flat(f"ytsearch{limit}:{keyword}", limit)


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #
def search(
    query: str,
    *,
    platform: str = "auto",
    region: str = "BR",
    limit: int = 18,
) -> dict[str, Any]:
    """Descoberta unificada: keyword, `@perfil` ou URL direta."""
    query = (query or "").strip()
    platform = platform if platform in PLATFORMS else "auto"
    limit = max(1, min(int(limit or 18), 40))
    region = (region or "BR").upper()[:2]

    if not query:
        return {"query": "", "platform": platform, "region": region, "results": [], "sources": []}

    raw: list[dict[str, Any]] = []
    sources: list[str] = []
    fallback = "youtube" if platform == "youtube" else "tiktok"

    if query.startswith("http://") or query.startswith("https://"):
        raw = _single_url(query)
        fallback = _platform_of(query, fallback)
        sources.append("url-direta")
    elif query.startswith("@"):
        raw = _tiktok_profile(query, limit)
        fallback = "tiktok"
        sources.append("tiktok-perfil")
        if not raw:
            raw = _youtube_keyword(query.lstrip("@"), limit)
            fallback = "youtube"
            sources.append("youtube-busca")
    else:
        if platform in ("auto", "tiktok"):
            found = _tiktok_keyword(query, limit)
            if found:
                raw.extend(found)
                sources.append("tiktok-tag")
        if platform in ("auto", "youtube") or not raw:
            found = _youtube_keyword(f"{query} {region}".strip(), limit)
            if found:
                raw.extend(found)
                sources.append("youtube-busca")
                if not any(s.startswith("tiktok") for s in sources):
                    fallback = "youtube"

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw:
        card = _normalize(entry, fallback)
        if not card:
            continue
        key = card["url"] or card["id"]
        if key in seen:
            continue
        seen.add(key)
        results.append(card)

    results.sort(key=lambda c: c["views"], reverse=True)
    return {
        "query": query,
        "platform": platform,
        "region": region,
        "results": results[:limit],
        "sources": sources,
    }
