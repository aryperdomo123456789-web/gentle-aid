"""Cofre de chaves de API do Ecossistema Viral.

As chaves ficam em `fabrica_clips/_config/api_keys.json` (fora do Git) e podem
ser sobrescritas por variáveis de ambiente. O restante do backend deve ler as
chaves SEMPRE por `api_keys.get_key("groq")` — nunca com os.environ direto.
"""

from __future__ import annotations

import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ..config import config

_lock = threading.Lock()

# --- Catálogo declarativo ----------------------------------------------------
# auth: "bearer" | "header" | "query" | "none"
PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "category": "LLM",
        "env": "DEEPSEEK_API_KEY",
        "docs": "https://api-docs.deepseek.com/",
        "usage": "Fallback barato para análise de texto, ranking e geração estruturada.",
        "prefix": "sk-",
        "test": {"url": "https://api.deepseek.com/models", "auth": "bearer"},
    },
    {
        "id": "gemini",
        "name": "Google Gemini",
        "category": "LLM",
        "env": "GEMINI_API_KEY",
        "docs": "https://ai.google.dev/gemini-api/docs",
        "usage": "Geração de roteiros, títulos e análise multimodal de clipes.",
        "test": {
            "url": "https://generativelanguage.googleapis.com/v1beta/models",
            "auth": "query",
            "param": "key",
        },
    },
    {
        "id": "groq",
        "name": "Groq",
        "category": "Transcrição / LLM",
        "env": "GROQ_API_KEY",
        "docs": "https://console.groq.com/docs/overview",
        "usage": "Transcrição Whisper-large em alta velocidade e LLM de baixa latência.",
        "prefix": "gsk_",
        "test": {"url": "https://api.groq.com/openai/v1/models", "auth": "bearer"},
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "category": "LLM",
        "env": "OPENROUTER_API_KEY",
        "docs": "https://openrouter.ai/docs/quickstart",
        "usage": "Roteador multi-modelo — fallback quando um provedor cai.",
        "prefix": "sk-or-",
        "test": {"url": "https://openrouter.ai/api/v1/key", "auth": "bearer"},
    },
    {
        "id": "mistral",
        "name": "Mistral",
        "category": "LLM",
        "env": "MISTRAL_API_KEY",
        "docs": "https://docs.mistral.ai/",
        "usage": "Classificação, resumo e geração alternativa.",
        "test": {"url": "https://api.mistral.ai/v1/models", "auth": "bearer"},
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow",
        "category": "LLM",
        "env": "SILICONFLOW_API_KEY",
        "docs": "https://docs.siliconflow.com/en/userguide/introduction",
        "usage": "Modelos open-source hospedados (fallback de custo).",
        "prefix": "sk-",
        "test": {"url": "https://api.siliconflow.com/v1/models", "auth": "bearer"},
    },
    {
        "id": "huggingface",
        "name": "Hugging Face",
        "category": "LLM / Modelos",
        "env": "HUGGINGFACE_API_KEY",
        "docs": "https://huggingface.co/docs",
        "usage": "Download de modelos RVC/Coqui e inferência serverless.",
        "prefix": "hf_",
        "test": {"url": "https://huggingface.co/api/whoami-v2", "auth": "bearer"},
    },
    {
        "id": "cohere",
        "name": "Cohere",
        "category": "Rerank",
        "env": "COHERE_API_KEY",
        "docs": "https://docs.cohere.com/",
        "usage": "Reranking de candidatos de pesquisa e de trechos virais.",
        "test": {"url": "https://api.cohere.com/v1/models", "auth": "bearer"},
    },
    {
        "id": "tavily",
        "name": "Tavily",
        "category": "Pesquisa Web",
        "env": "TAVILY_API_KEY",
        "docs": "https://docs.tavily.com/welcome",
        "usage": "Busca rápida de tendências por nicho (roda em paralelo com a Exa).",
        "prefix": "tvly-",
        "test": {"url": "https://api.tavily.com/search", "auth": "bearer", "method": "POST",
                  "body": {"query": "ping", "max_results": 1}},
    },
    {
        "id": "exa",
        "name": "Exa",
        "category": "Pesquisa Web",
        "env": "EXA_API_KEY",
        "docs": "https://exa.ai/docs/reference/search-api-guide",
        "usage": "Segunda opinião de pesquisa, mais profunda e com citação.",
        "test": {"url": "https://api.exa.ai/search", "auth": "header", "header": "x-api-key",
                  "method": "POST", "body": {"query": "ping", "numResults": 1}},
    },
    {
        "id": "firecrawl",
        "name": "Firecrawl",
        "category": "Extração",
        "env": "FIRECRAWL_API_KEY",
        "docs": "https://docs.firecrawl.dev/introduction",
        "usage": "Crawl e scrape de páginas inteiras para alimentar o radar.",
        "prefix": "fc-",
        "test": {"url": "https://api.firecrawl.dev/v1/team/credit-usage", "auth": "bearer"},
    },
    {
        "id": "jina",
        "name": "Jina Reader",
        "category": "Extração",
        "env": "JINA_API_KEY",
        "docs": "https://jina.ai/serve/",
        "usage": "Converte páginas em markdown limpo e gera embeddings.",
        "prefix": "jina_",
        "test": {"url": "https://r.jina.ai/https://example.com", "auth": "bearer"},
    },
    {
        "id": "langfuse",
        "name": "Langfuse",
        "category": "Observabilidade",
        "env": "LANGFUSE_SECRET_KEY",
        "docs": "https://langfuse.com/docs/api-and-data-platform/features/public-api",
        "usage": "Rastreio de job_id, custo, latência, modelo e resultado final.",
        "prefix": "sk-lf-",
        "test": None,
    },
    {
        "id": "cloudflare",
        "name": "Cloudflare Workers",
        "category": "Infra",
        "env": "CLOUDFLARE_API_TOKEN",
        "docs": "https://developers.cloudflare.com/workers/",
        "usage": "Endpoints leves, cache e camada pública de webhooks.",
        "test": {"url": "https://api.cloudflare.com/client/v4/user/tokens/verify", "auth": "bearer"},
    },
    {
        "id": "whisper",
        "name": "Whisper API",
        "category": "Transcrição",
        "env": "WHISPER_API_KEY",
        "docs": "https://whisper-api.com/docs/",
        "usage": "Fallback de transcrição quando a Groq falha ou estoura limite.",
        "test": None,
    },
    {
        "id": "tikapi",
        "name": "TikAPI",
        "category": "TikTok",
        "env": "TIKAPI_KEY",
        "docs": "https://tikapi.io/",
        "usage": "Radar de tendências e metadados de vídeos do TikTok.",
        "test": None,
    },
    {
        "id": "lamatok",
        "name": "Lamatok",
        "category": "TikTok",
        "env": "LAMATOK_API_KEY",
        "docs": "https://api.lamatok.com/docs",
        "usage": "Download direto de mídia do TikTok por URL.",
        "test": None,
    },
]

PROVIDER_BY_ID = {p["id"]: p for p in PROVIDERS}


# --- Persistência ------------------------------------------------------------
def _store_file():
    path = config.storage_dir / "_config" / "api_keys.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load() -> dict[str, dict[str, Any]]:
    file = _store_file()
    if not file.exists():
        return {}
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(data: dict[str, dict[str, Any]]) -> None:
    file = _store_file()
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(file, 0o600)
    except OSError:
        pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 10:
        return key[:2] + "•" * 6
    return f"{key[:6]}{'•' * 8}{key[-4:]}"


def get_key(provider_id: str) -> str | None:
    """Fonte única de verdade para o resto do backend."""
    provider = PROVIDER_BY_ID.get(provider_id)
    if not provider:
        return None
    with _lock:
        stored = _load().get(provider_id, {})
    key = stored.get("key") or os.environ.get(provider["env"], "")
    return key or None


def set_key(provider_id: str, key: str, note: str = "") -> dict[str, Any]:
    with _lock:
        data = _load()
        entry = data.get(provider_id, {})
        entry.update({"key": key.strip(), "note": note.strip(), "updated_at": _now()})
        entry.pop("last_test", None)
        data[provider_id] = entry
        _save(data)
    return describe(provider_id)


def delete_key(provider_id: str) -> dict[str, Any]:
    with _lock:
        data = _load()
        data.pop(provider_id, None)
        _save(data)
    return describe(provider_id)


def _record_test(provider_id: str, result: dict[str, Any]) -> None:
    with _lock:
        data = _load()
        entry = data.setdefault(provider_id, {})
        entry["last_test"] = result
        _save(data)


def describe(provider_id: str) -> dict[str, Any]:
    provider = PROVIDER_BY_ID[provider_id]
    with _lock:
        stored = _load().get(provider_id, {})
    stored_key = stored.get("key") or ""
    env_key = os.environ.get(provider["env"], "")
    key = stored_key or env_key
    return {
        "id": provider["id"],
        "name": provider["name"],
        "category": provider["category"],
        "env": provider["env"],
        "docs": provider["docs"],
        "usage": provider["usage"],
        "prefix": provider.get("prefix"),
        "testable": bool(provider.get("test")),
        "configured": bool(key),
        "source": "cofre" if stored_key else ("env" if env_key else "vazio"),
        "masked": mask(key),
        "note": stored.get("note", ""),
        "updated_at": stored.get("updated_at"),
        "last_test": stored.get("last_test"),
    }


def list_all() -> list[dict[str, Any]]:
    return [describe(p["id"]) for p in PROVIDERS]


# --- Teste de conectividade --------------------------------------------------
def test_provider(provider_id: str) -> dict[str, Any]:
    provider = PROVIDER_BY_ID[provider_id]
    spec = provider.get("test")
    key = get_key(provider_id)

    if not key:
        result = {"ok": False, "status": 0, "message": "Nenhuma chave configurada.", "at": _now()}
        _record_test(provider_id, result)
        return result
    if not spec:
        result = {
            "ok": None,
            "status": 0,
            "message": "Provedor sem endpoint de teste — validação manual.",
            "at": _now(),
        }
        _record_test(provider_id, result)
        return result

    url = spec["url"]
    headers = {"Accept": "application/json", "User-Agent": "EcossistemaViral/1.0"}
    body = None
    method = spec.get("method", "GET")

    auth = spec.get("auth")
    if auth == "bearer":
        headers["Authorization"] = f"Bearer {key}"
    elif auth == "header":
        headers[spec.get("header", "x-api-key")] = key
    elif auth == "query":
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{spec.get('param', 'key')}={key}"

    if spec.get("body") is not None:
        body = json.dumps(spec["body"]).encode()
        headers["Content-Type"] = "application/json"

    started = time.perf_counter()
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            status = resp.status
            resp.read(2048)
        ok, message = True, "Chave válida e respondendo."
    except urllib.error.HTTPError as exc:
        status = exc.code
        ok = status not in (401, 402, 403, 429)
        message = {
            401: "Chave inválida ou revogada (401).",
            402: "Créditos esgotados / pagamento pendente (402).",
            403: "Sem permissão para este recurso (403).",
            429: "Limite de requisições atingido (429).",
        }.get(status, f"Endpoint respondeu HTTP {status}.")
    except urllib.error.URLError as exc:
        status, ok = 0, False
        message = f"Falha de rede: {exc.reason}"
    except Exception as exc:  # noqa: BLE001
        status, ok = 0, False
        message = f"Erro inesperado: {exc}"

    result = {
        "ok": ok,
        "status": status,
        "message": message,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "at": _now(),
    }
    _record_test(provider_id, result)
    return result
