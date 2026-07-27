"""Motor de tendências reais + previsão de nichos.

Fontes (todas opcionais e independentes — se uma cair, as outras seguem):
  1. Google Trends RSS  → o que o povo está pesquisando AGORA (sem chave).
  2. YouTube (yt-dlp)   → vídeos com tração real, com view_count e velocidade.
  3. Tavily / Exa       → pesquisa web de sinais de tendência (usa Central de APIs).
  4. LLM (DeepSeek/Groq/OpenRouter) → previsão de nichos para os próximos meses,
     ancorada nos sinais coletados acima. Sem chave, cai numa heurística local.
"""

from __future__ import annotations

import json
import math
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from ..config import config
from . import api_keys, media

_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_LOCK = threading.Lock()
DEFAULT_TTL = 120  # 2 min, para o radar ficar mais vivo


# --------------------------------------------------------------------------- #
# infra
# --------------------------------------------------------------------------- #
def _cached(key: str, ttl: int, producer: Callable[[], Any]) -> Any:
    now = time.time()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = producer()
    with _CACHE_LOCK:
        _CACHE[key] = (now, value)
    return value


def _http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
               body: dict[str, Any] | None = None, timeout: int = 20) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "EcossistemaViral/1.0")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310
        return json.loads(res.read().decode("utf-8", "replace"))


def _http_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 EcossistemaViral"})
    with urllib.request.urlopen(req, timeout=timeout) as res:  # noqa: S310
        return res.read().decode("utf-8", "replace")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _compact(value: int) -> str:
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= limit:
            return f"{value / limit:.1f}".rstrip("0").rstrip(".") + suffix
    return str(value)


_STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "no",
    "nos",
    "na",
    "nas",
    "para",
    "por",
    "que",
    "um",
    "uma",
    "the",
    "of",
    "and",
    "to",
    "for",
    "with",
    "on",
    "in",
    "at",
}


def _normalize_topic(text: str, max_words: int = 6) -> str:
    words = [w.lower() for w in re.findall(r"[0-9A-Za-zÀ-ÿ]+", text or "")]
    filtered = [w for w in words if w not in _STOPWORDS and len(w) > 1]
    if not filtered:
        filtered = words
    return " ".join(filtered[:max_words]).strip()


def _topic_words(text: str) -> set[str]:
    return set(_normalize_topic(text).split())


def _traffic_value(value: str | int | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return max(value, 0)
    digits = re.sub(r"[^0-9]", "", str(value))
    if not digits:
        return 0
    try:
        return int(digits)
    except ValueError:
        return 0


def _title_case(text: str) -> str:
    chunks = re.split(r"(\s+)", (text or "").strip())
    out: list[str] = []
    for chunk in chunks:
        if not chunk or chunk.isspace():
            out.append(chunk)
            continue
        if chunk.isupper() or chunk.isdigit():
            out.append(chunk)
        else:
            out.append(chunk[:1].upper() + chunk[1:])
    return "".join(out).strip()


def _score_topic_match(topic: str, text: str) -> int:
    topic_words = _topic_words(topic)
    text_words = _topic_words(text)
    if not topic_words or not text_words:
        return 0
    overlap = len(topic_words & text_words)
    if overlap:
        return overlap * 3
    topic_norm = _normalize_topic(topic)
    text_norm = _normalize_topic(text)
    if topic_norm and topic_norm in text_norm:
        return max(1, len(topic_norm.split()))
    if text_norm and text_norm in topic_norm:
        return max(1, len(text_norm.split()))
    return 0


# --------------------------------------------------------------------------- #
# 1. Google Trends (RSS público, sem chave)
# --------------------------------------------------------------------------- #
_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
_TAG_RE = re.compile(r"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", re.S)


def _xml_field(block: str, tag: str) -> str:
    m = re.search(_TAG_RE.pattern.format(tag=tag), block, re.S)
    return (m.group(1).strip() if m else "").replace("&amp;", "&")


def google_trends(region: str = "BR", limit: int = 20) -> list[dict[str, Any]]:
    """Buscas em alta no país, direto do feed oficial do Google Trends."""
    geo = (region or "BR").upper()[:2]
    out: list[dict[str, Any]] = []
    for url in (
        f"https://trends.google.com/trending/rss?geo={geo}",
        f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}",
    ):
        try:
            xml = _http_text(url)
        except Exception:  # noqa: BLE001
            continue
        for block in _ITEM_RE.findall(xml)[:limit]:
            title = _xml_field(block, "title")
            if not title:
                continue
            traffic = _xml_field(block, "ht:approx_traffic") or ""
            news = _xml_field(block, "ht:news_item_title")
            out.append(
                {
                    "term": title,
                    "traffic": traffic or "—",
                    "context": news or "",
                    "source": "google-trends",
                    "search_url": "https://www.google.com/search?q=" + urllib.parse.quote(title),
                }
            )
        if out:
            break
    return out[:limit]


# --------------------------------------------------------------------------- #
# 2. YouTube via yt-dlp — vídeos com tração real
# --------------------------------------------------------------------------- #
def _ytdlp_json(target: str, limit: int, timeout: int = 120) -> list[dict[str, Any]]:
    raw = media.run(
        [
            config.ytdlp_bin,
            "--flat-playlist",
            "--dump-single-json",
            "--no-warnings",
            "--playlist-end",
            str(limit),
            target,
        ],
        timeout=timeout,
    )
    if "{" not in raw:
        return []
    data = json.loads(raw[raw.index("{"):])
    return [e for e in (data.get("entries") or []) if isinstance(e, dict)]


def _video_from_entry(entry: dict[str, Any], origin: str) -> dict[str, Any]:
    views = int(entry.get("view_count") or 0)
    duration = int(entry.get("duration") or 0)
    vid = entry.get("id") or ""
    url = entry.get("url") or entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
    embed_url = None
    if origin.startswith("tiktok") and vid:
        embed_url = f"https://www.tiktok.com/player/v1/{vid}?music_info=1&description=1"
    elif vid:
        embed_url = f"https://www.youtube.com/embed/{vid}"
    return {
        "id": vid,
        "title": entry.get("title") or "Sem título",
        "author": entry.get("uploader") or entry.get("channel") or "desconhecido",
        "views": views,
        "views_human": _compact(views),
        "likes": int(entry.get("like_count") or 0),
        "duration": duration,
        "is_short": bool(duration and duration <= 60),
        "url": url,
        "embed_url": embed_url,
        "thumbnail": (entry.get("thumbnails") or [{}])[-1].get("url") if entry.get("thumbnails") else None,
        "source": origin,
    }


def _youtube_search(keyword: str, limit: int, *, origin: str = "youtube-search") -> list[dict[str, Any]]:
    query = re.sub(r"\s+", " ", (keyword or "")).strip()
    if not query:
        return []
    try:
        entries = _ytdlp_json(f"ytsearch{max(limit, 1) * 2}:{query}", max(limit, 1) * 2)
    except Exception:  # noqa: BLE001
        return []
    videos = [_video_from_entry(e, origin) for e in entries]
    return sorted(videos, key=lambda v: v["views"], reverse=True)[:limit]


def youtube_trending(region: str = "BR", limit: int = 15) -> list[dict[str, Any]]:
    """Aba oficial de 'Em alta' do YouTube — o que já está viralizando."""
    try:
        entries = _ytdlp_json("https://www.youtube.com/feed/trending", limit)
    except Exception:  # noqa: BLE001
        entries = []
    videos = [_video_from_entry(e, "youtube-trending") for e in entries]
    videos = sorted(videos, key=lambda v: v["views"], reverse=True)[:limit]
    if videos:
        return videos

    geo = (region or "BR").upper()[:2]
    fallback_queries = [
        f"youtube em alta {geo}",
        f"trending youtube {geo}",
        f"youtube trending {geo}",
    ]
    for trend in google_trends(region, 4):
        term = (trend.get("term") or "").strip()
        if term:
            fallback_queries.append(f"{term} {geo}")
            fallback_queries.append(term)

    fallback: list[dict[str, Any]] = []
    seen: set[str] = set()
    for keyword in fallback_queries:
        for video in _youtube_search(keyword, max(3, limit // 2), origin="youtube-trending-fallback"):
            key = video["url"] or video["id"]
            if key in seen:
                continue
            seen.add(key)
            fallback.append(video)
            if len(fallback) >= limit:
                return fallback

    return fallback


def youtube_niche(nicho: str, limit: int = 15, *, shorts_only: bool = False) -> list[dict[str, Any]]:
    """Vídeos recentes do nicho ordenados por tração (views)."""
    query = f"{nicho} shorts" if shorts_only else nicho
    target = f"ytsearchdate{limit * 2}:{query}"
    try:
        entries = _ytdlp_json(target, limit * 2)
    except Exception:  # noqa: BLE001
        entries = []
    videos = [_video_from_entry(e, "youtube-search") for e in entries]
    if shorts_only:
        videos = [v for v in videos if v["is_short"] or "short" in v["title"].lower()] or videos
    videos = sorted(videos, key=lambda v: v["views"], reverse=True)[:limit]
    if videos:
        return videos

    fallback = _youtube_search(f"{nicho} {query}".strip(), limit, origin="youtube-search-fallback")
    if shorts_only:
        filtered = [v for v in fallback if v["is_short"] or "short" in v["title"].lower()]
        if filtered:
            fallback = filtered
    return fallback[:limit]


def tiktok_niche(nicho: str, region: str = "BR", limit: int = 12) -> list[dict[str, Any]]:
    """Virais do TikTok pelo nicho — usa yt-dlp na busca do próprio TikTok
    e cai para a busca do YouTube (clipes reuploadados) se o TikTok bloquear."""
    tag = re.sub(r"[^0-9a-zA-Z]+", "", nicho)[:40]
    if tag:
        try:
            entries = _ytdlp_json(f"https://www.tiktok.com/tag/{tag}", limit)
            videos = [_video_from_entry(e, "tiktok-tag") for e in entries if e.get("id")]
            if videos:
                return sorted(videos, key=lambda v: v["views"], reverse=True)[:limit]
        except Exception:  # noqa: BLE001
            pass
    return youtube_niche(f"{nicho} tiktok {region}", limit, shorts_only=True)


# --------------------------------------------------------------------------- #
# 3. Pesquisa web (Tavily + Exa em paralelo)
# --------------------------------------------------------------------------- #
def web_signals(nicho: str, region: str = "BR", limit: int = 6) -> dict[str, Any]:
    query = (
        f"tendências virais {nicho} {region} redes sociais "
        f"{datetime.now(timezone.utc).strftime('%B %Y')}"
    )
    results: list[dict[str, Any]] = []
    providers: list[dict[str, Any]] = []

    tavily = api_keys.get_key("tavily")
    if tavily:
        started = time.time()
        try:
            data = _http_json(
                "https://api.tavily.com/search",
                method="POST",
                headers={"Authorization": f"Bearer {tavily}"},
                body={"query": query, "max_results": limit, "search_depth": "basic",
                      "topic": "news", "days": 30},
            )
            items = [
                {"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": (r.get("content") or "")[:400], "provider": "tavily",
                 "score": float(r.get("score") or 0)}
                for r in (data.get("results") or [])
            ]
            results += items
            providers.append({"provider": "tavily", "ok": True,
                              "results": len(items), "latency_ms": int((time.time() - started) * 1000)})
        except Exception as exc:  # noqa: BLE001
            providers.append({"provider": "tavily", "ok": False, "error": str(exc)[:160]})
    else:
        providers.append({"provider": "tavily", "ok": False, "error": "sem chave configurada"})

    exa = api_keys.get_key("exa")
    if exa:
        started = time.time()
        try:
            data = _http_json(
                "https://api.exa.ai/search",
                method="POST",
                headers={"x-api-key": exa},
                body={"query": query, "numResults": limit, "type": "auto",
                      "contents": {"text": {"maxCharacters": 400}}},
            )
            items = [
                {"title": r.get("title", ""), "url": r.get("url", ""),
                 "snippet": (r.get("text") or "")[:400], "provider": "exa",
                 "score": float(r.get("score") or 0)}
                for r in (data.get("results") or [])
            ]
            results += items
            providers.append({"provider": "exa", "ok": True,
                              "results": len(items), "latency_ms": int((time.time() - started) * 1000)})
        except Exception as exc:  # noqa: BLE001
            providers.append({"provider": "exa", "ok": False, "error": str(exc)[:160]})
    else:
        providers.append({"provider": "exa", "ok": False, "error": "sem chave configurada"})

    results.sort(key=lambda r: r["score"], reverse=True)
    chosen = next((p["provider"] for p in providers if p.get("ok") and p.get("results")), None)
    return {"query": query, "results": results[: limit * 2], "providers": providers, "chosen": chosen}


def _evidence_bucket(*parts: str) -> str:
    text = " ".join(p for p in parts if p)
    return _normalize_topic(text)


def _build_viral_intelligence(
    nicho: str,
    region: str,
    trends: list[dict[str, Any]],
    youtube_trending_videos: list[dict[str, Any]],
    niche_videos: list[dict[str, Any]],
    tiktok_videos: list[dict[str, Any]],
    web: dict[str, Any],
    limit: int = 12,
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add_candidate(
        label: str,
        *,
        source: str,
        score: float,
        evidence: str,
        url: str | None = None,
        format_hint: str | None = None,
        horizon: str | None = None,
    ) -> None:
        key = _evidence_bucket(label)
        if not key:
            return
        item = candidates.setdefault(
            key,
            {
                "topic": _title_case(label or key),
                "score": 0.0,
                "sources": set(),
                "evidence": [],
                "urls": set(),
                "formats": set(),
                "horizons": set(),
            },
        )
        item["score"] += float(score)
        item["sources"].add(source)
        if evidence and evidence not in item["evidence"]:
            item["evidence"].append(evidence)
        if url:
            item["urls"].add(url)
        if format_hint:
            item["formats"].add(format_hint)
        if horizon:
            item["horizons"].add(horizon)

    if nicho:
        niche_score = 18 + len(_topic_words(nicho)) * 4
        add_candidate(
            nicho,
            source="nicho-base",
            score=niche_score,
            evidence=f"Nicho pesquisado pelo operador: {nicho}.",
            horizon="30 dias",
        )

    for idx, trend in enumerate(trends[:12]):
        traffic = _traffic_value(trend.get("traffic"))
        trend_score = 22 + math.log10(traffic + 10) * 13 + max(0, 10 - idx) * 1.2
        add_candidate(
            trend.get("term", ""),
            source="google-trends",
            score=trend_score,
            evidence=f"Google Trends: {trend.get('traffic', '—')}{' · ' + trend['context'] if trend.get('context') else ''}",
            url=trend.get("search_url"),
            horizon="7 dias" if traffic >= 100000 else "30 dias",
        )

    def add_video_candidates(videos: list[dict[str, Any]], source: str) -> None:
        for idx, video in enumerate(videos[:12]):
            views = int(video.get("views") or 0)
            base = 10 + math.log10(views + 10) * 5.5
            if video.get("is_short"):
                base += 4
            base += max(0, 10 - idx) * 0.8
            if source == "youtube-em-alta" and not nicho:
                base *= 0.75
            topic_seed = _normalize_topic(str(video.get("title") or ""), 5)
            if topic_seed:
                add_candidate(
                    topic_seed,
                    source=source,
                    score=base,
                    evidence=f"{video.get('title', 'Sem título')} · {video.get('views_human', '—')} views",
                    url=str(video.get("url") or ""),
                    format_hint="Short 15-30s" if video.get("is_short") else "Vídeo 30-90s",
                    horizon="7 dias" if video.get("is_short") else "30 dias",
                )
            if nicho:
                niche_score = _score_topic_match(nicho, str(video.get("title") or ""))
                if niche_score:
                    add_candidate(
                        nicho,
                        source=source,
                        score=(base * 0.55) + niche_score * 8,
                        evidence=f"Vídeo relacionado ao nicho: {video.get('title', 'Sem título')} · {video.get('views_human', '—')} views",
                        url=str(video.get("url") or ""),
                        format_hint="Short 15-30s" if video.get("is_short") else "Vídeo 30-90s",
                        horizon="30 dias",
                    )

    add_video_candidates(youtube_trending_videos, "youtube-em-alta")
    add_video_candidates(niche_videos, "youtube-nicho")
    add_video_candidates(tiktok_videos, "tiktok")

    for idx, result in enumerate(web["results"][:12]):
        title = str(result.get("title") or "").strip()
        if not title:
            continue
        score = 18 + float(result.get("score") or 0) * 18 + max(0, 8 - idx) * 1.2
        add_candidate(
            _normalize_topic(title, 6),
            source=str(result.get("provider") or "web"),
            score=score,
            evidence=f"{result.get('provider', 'web')}: {title}",
            url=str(result.get("url") or ""),
            format_hint="Pesquisa / contexto",
            horizon="60 dias",
        )

    ranked: list[dict[str, Any]] = []
    for item in candidates.values():
        sources = sorted(item["sources"])
        source_count = len(sources)
        raw_score = float(item["score"]) + max(0, source_count - 1) * 16
        norm_score = int(round(min(99.0, max(18.0, raw_score))))
        evidence = item["evidence"][:3]
        if source_count >= 3:
            why = f"Convergência em {source_count} fontes com sinais fortes: {', '.join(evidence[:2])}."
        elif source_count == 2:
            why = f"Aponta em duas fontes com boa coerência: {', '.join(evidence[:2])}."
        else:
            why = f"Sinal forte isolado, mas promissor: {evidence[0] if evidence else 'sem evidência detalhada'}."

        formats = sorted(item["formats"]) or ["Short 15-30s", "Reels 30-45s"]
        horizon = sorted(item["horizons"])[0] if item["horizons"] else "30 dias"
        ranked.append(
            {
                "topic": item["topic"],
                "score": norm_score,
                "confidence": norm_score,
                "horizon": horizon,
                "because": why,
                "signals": evidence,
                "sources": sources,
                "formats": formats,
                "search_url": "https://www.google.com/search?q="
                + urllib.parse.quote(item["topic"]),
                "region": region,
            }
        )

    ranked.sort(
        key=lambda row: (
            row["score"],
            len(row["sources"]),
            row["topic"].lower(),
        ),
        reverse=True,
    )
    return ranked[:limit]


# --------------------------------------------------------------------------- #
# 4. Previsão de nichos (LLM com fallback heurístico)
# --------------------------------------------------------------------------- #
_LLM_ROUTES = [
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "deepseek/deepseek-chat"),
    ("mistral", "https://api.mistral.ai/v1/chat/completions", "mistral-large-latest"),
    ("siliconflow", "https://api.siliconflow.com/v1/chat/completions", "deepseek-ai/DeepSeek-V3"),
]

_PROMPT = """Você é analista sênior de tendências de conteúdo curto (TikTok, Reels, Shorts).
Sinais coletados agora ({now}) para a região {region}, nicho base "{nicho}":

BUSCAS EM ALTA (Google Trends):
{trends}

VÍDEOS COM TRAÇÃO REAL:
{videos}

NOTÍCIAS / PESQUISA WEB:
{web}

INTELIGÊNCIA DE MERCADO (ranking interno):
{intelligence}

Responda SOMENTE JSON válido no formato:
{{"forecast":[{{"nicho":"...","horizonte":"30 dias|60 dias|90 dias","confianca":0-100,
"porque":"1-2 frases com base nos sinais","angulos":["ideia de vídeo 1","ideia 2","ideia 3"],
"hashtags":["#..."],"formato":"Short 15-30s | Reels 45s | ..."}}]}}
Traga de 5 a 7 nichos, do mais provável ao menos provável. Português do Brasil, direto."""


def _llm_json(prompt: str, timeout: int = 60) -> tuple[dict[str, Any] | None, str | None]:
    routes = {pid: (url, model) for pid, url, model in _LLM_ROUTES}
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
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
            content = data["choices"][0]["message"]["content"]
            start, end = content.find("{"), content.rfind("}")
            if start == -1 or end == -1:
                continue
            return json.loads(content[start : end + 1]), provider
        except Exception:  # noqa: BLE001
            continue
    return None, None


def _heuristic_forecast(nicho: str, trends: list[dict], videos: list[dict]) -> list[dict[str, Any]]:
    """Sem chave de LLM o radar ainda entrega: ranqueia sinais reais coletados."""
    out: list[dict[str, Any]] = []
    for t in trends[:4]:
        out.append(
            {
                "nicho": f"{nicho} + {t['term']}",
                "horizonte": "30 dias",
                "confianca": 70,
                "porque": f"'{t['term']}' está em alta nas buscas ({t['traffic']}) e ainda tem pouco vídeo curto cobrindo o assunto.",
                "angulos": [
                    f"Explicação rápida de '{t['term']}' aplicada a {nicho}",
                    f"Reação/opinião polêmica sobre '{t['term']}'",
                    f"Lista de 3 erros sobre '{t['term']}'",
                ],
                "hashtags": ["#" + re.sub(r"[^0-9a-zA-Z]+", "", t["term"].lower())[:24] or "#viral", "#fyp"],
                "formato": "Short 15-30s",
                "fonte": "heurística local (Google Trends)",
            }
        )
    for v in videos[:3]:
        out.append(
            {
                "nicho": f"{nicho}: formato de '{v['title'][:48]}'",
                "horizonte": "60 dias",
                "confianca": 60,
                "porque": f"Vídeo com {v['views_human']} views mostra que o formato ainda está performando e cabe clonagem de estrutura.",
                "angulos": ["Mesma estrutura, outro exemplo", "Versão contrária do gancho", "Parte 2 do tema"],
                "hashtags": ["#fyp", "#viral"],
                "formato": "Short 30-45s" if v["is_short"] else "Reels 45-60s",
                "fonte": "heurística local (tração real)",
            }
        )
    return out


def forecast(nicho: str, region: str = "BR") -> dict[str, Any]:
    trends = google_trends(region, 12)
    videos = youtube_niche(nicho, 10) if nicho else youtube_trending(region, 10)
    trending = youtube_trending(region, 10)
    tiktok = tiktok_niche(nicho, region, 8) if nicho else []
    web = web_signals(nicho or "conteúdo viral", region)
    intelligence = _build_viral_intelligence(
        nicho or "conteúdo viral",
        region,
        trends,
        trending,
        videos,
        tiktok,
        web,
        limit=8,
    )

    prompt = _PROMPT.format(
        now=_now_iso(),
        region=region,
        nicho=nicho or "geral",
        trends="\n".join(f"- {t['term']} ({t['traffic']})" for t in trends[:12]) or "- sem dados",
        videos="\n".join(f"- {v['title']} — {v['views_human']} views (@{v['author']})" for v in videos[:10])
        or "- sem dados",
        web="\n".join(f"- {r['title']}: {r['snippet'][:180]}" for r in web["results"][:6]) or "- sem dados",
        intelligence="\n".join(
            f"- {item['topic']} [{item['score']}]: {item['because']}" for item in intelligence[:6]
        )
        or "- sem dados",
    )

    data, provider = _llm_json(prompt)
    items = (data or {}).get("forecast") if isinstance(data, dict) else None
    if not items:
        items = [
            {
                "nicho": item["topic"],
                "horizonte": item["horizon"],
                "confianca": item["confidence"],
                "porque": item["because"],
                "angulos": [
                    f"Abrir com o gancho: {item['topic']}",
                    "Mostrar prova rápida e exemplo prático",
                    "Fechar com CTA para salvar e compartilhar",
                ],
                "hashtags": ["#" + re.sub(r"[^0-9a-zA-Z]+", "", item["topic"].lower())[:24] or "#viral", "#fyp"],
                "formato": item["formats"][0] if item.get("formats") else "Short 15-30s",
                "fonte": "motor inteligente",
            }
            for item in intelligence[:6]
        ] or _heuristic_forecast(nicho or "conteúdo viral", trends, videos)
        provider = None

    return {
        "nicho": nicho,
        "region": region,
        "generated_at": _now_iso(),
        "engine": provider or "heurística local",
        "forecast": items,
        "signals": {"trends": trends[:12], "videos": videos[:10], "web": web, "intelligence": intelligence},
    }


# --------------------------------------------------------------------------- #
# Radar global agregado
# --------------------------------------------------------------------------- #
def radar(nicho: str = "", region: str = "BR", *, refresh: bool = False) -> dict[str, Any]:
    key = f"radar:{region}:{nicho.lower()}"
    if refresh:
        with _CACHE_LOCK:
            _CACHE.pop(key, None)

    def build() -> dict[str, Any]:
        trends = google_trends(region, 20)
        trending = youtube_trending(region, 12)
        niche_videos = youtube_niche(nicho, 12) if nicho else []
        tiktok = tiktok_niche(nicho, region, 10) if nicho else []
        web = web_signals(nicho or "conteúdo viral", region)
        intelligence = _build_viral_intelligence(
            nicho or "conteúdo viral",
            region,
            trends,
            trending,
            niche_videos,
            tiktok,
            web,
            limit=12,
        )
        return {
            "region": region,
            "nicho": nicho,
            "generated_at": _now_iso(),
            "searches": trends,
            "youtube_trending": trending,
            "niche_videos": niche_videos,
            "tiktok": tiktok,
            "web": web,
            "intelligence": intelligence,
            "sources": [
                {"name": "Google Trends", "ok": bool(trends), "items": len(trends)},
                {"name": "YouTube Em Alta", "ok": bool(trending), "items": len(trending)},
                {"name": "Busca de nicho", "ok": bool(niche_videos), "items": len(niche_videos)},
                {"name": "TikTok", "ok": bool(tiktok), "items": len(tiktok)},
                *[
                    {"name": p["provider"].title(), "ok": bool(p.get("ok")), "items": p.get("results", 0),
                     "error": p.get("error")}
                    for p in web["providers"]
                ],
            ],
        }

    return _cached(key, DEFAULT_TTL, build)
