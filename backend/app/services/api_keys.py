"""Cofre de chaves de API do Ecossistema Viral.

As chaves ficam em `fabrica_clips/_config/api_keys.json` (fora do Git) e podem
ser sobrescritas por variáveis de ambiente. O restante do backend deve ler as
chaves SEMPRE por `api_keys.get_key("groq")` — nunca com os.environ direto.
"""

from __future__ import annotations

import json
import re
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
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
        "prefix": "AIza",
        "format_hint": "A chave do Gemini (AI Studio) começa com 'AIza'. Tokens 'AQ.' ou 'ya29.' são credenciais OAuth do Google Cloud e não funcionam aqui.",
        "remediation": "Pegue a chave em aistudio.google.com/apikey (começa com AIza) e cole no campo abaixo.",
        # Doc oficial: autenticação por header x-goog-api-key.
        "test": [
            {
                "url": "https://generativelanguage.googleapis.com/v1beta/models",
                "auth": "header",
                "header": "x-goog-api-key",
            },
            {
                "url": "https://generativelanguage.googleapis.com/v1beta/models",
                "auth": "query",
                "param": "key",
            },
        ],
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
        "format_hint": "Use um Access Token do tipo 'Read' (Settings → Access Tokens). Tokens fine-grained sem escopo de leitura respondem 401.",
        "remediation": "Gere um novo token em huggingface.co/settings/tokens com tipo 'Read' e cole aqui — o token atual foi revogado.",
        "test": [
            {"url": "https://huggingface.co/api/whoami-v2", "auth": "bearer"},
        ],
    },
    {
        "id": "cohere",
        "name": "Cohere",
        "category": "Rerank",
        "env": "COHERE_API_KEY",
        "docs": "https://docs.cohere.com/reference/checkapikey",
        "usage": "Reranking de candidatos de pesquisa e de trechos virais.",
        "format_hint": "Chaves de trial da Cohere não têm acesso a /v1/models; o teste usa o endpoint oficial check-api-key.",
        "remediation": "Gere uma nova chave em dashboard.cohere.com → API Keys (Trial serve) e cole aqui.",
        "test": [
            {
                "url": "https://api.cohere.com/v1/check-api-key",
                "auth": "bearer",
                "method": "POST",
                "body": {},
                "expect_json": {"valid": True},
                "invalid_message": "A Cohere respondeu que esta chave não é válida (valid=false) — ela foi revogada ou pertence a outra conta.",
            },
            {
                "url": "https://api.cohere.ai/v1/check-api-key",
                "auth": "bearer",
                "method": "POST",
                "body": {},
                "expect_json": {"valid": True},
                "invalid_message": "A Cohere respondeu que esta chave não é válida (valid=false).",
            },
            {
                "url": "https://api.cohere.com/v1/tokenize",
                "auth": "bearer",
                "method": "POST",
                "body": {"text": "ping", "model": "command-r"},
            },
            {"url": "https://api.cohere.com/v1/models", "auth": "bearer"},
        ],
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
        "format_hint": "Requer também LANGFUSE_PUBLIC_KEY (pk-lf-...) — o teste usa Basic auth (public:secret).",
        # Basic auth pk:sk contra /api/public/projects.
        "test": [
            {
                "url": os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
                + "/api/public/projects",
                "auth": "basic",
                "basic_user_env": "LANGFUSE_PUBLIC_KEY",
            }
        ],
    },
    {
        "id": "cloudflare",
        "name": "Cloudflare Workers",
        "category": "Infra",
        "env": "CLOUDFLARE_API_TOKEN",
        "docs": "https://developers.cloudflare.com/api/operations/user-api-tokens-verify-token",
        "usage": "Endpoints leves, cache e camada pública de webhooks.",
        "format_hint": "Use um API Token (Meu Perfil → API Tokens). A Global API Key antiga só é aceita junto com CLOUDFLARE_EMAIL.",
        "shape_warn": {
            "pattern": r"^[0-9a-fA-F]{32,40}$",
            "message": "Esta credencial tem cara de Global API Key (32-40 caracteres hexadecimais), não de API Token.",
        },
        "remediation": "Gere um API Token em dash.cloudflare.com → Meu Perfil → API Tokens (template 'Edit Cloudflare Workers') e cole aqui. Se preferir manter a Global API Key, defina também CLOUDFLARE_EMAIL no .env.",
        "test": [
            {"url": "https://api.cloudflare.com/client/v4/user/tokens/verify", "auth": "bearer"},
            {"url": "https://api.cloudflare.com/client/v4/accounts", "auth": "bearer"},
            # Global API Key legada: exige e-mail da conta.
            {
                "url": "https://api.cloudflare.com/client/v4/user",
                "auth": "header",
                "header": "X-Auth-Key",
                "extra_headers_env": {"X-Auth-Email": "CLOUDFLARE_EMAIL"},
                "requires_env": ["CLOUDFLARE_EMAIL"],
            },
        ],
    },
    {
        "id": "whisper",
        "name": "Whisper API",
        "category": "Transcrição",
        "env": "WHISPER_API_KEY",
        "docs": "https://platform.openai.com/docs/api-reference/audio",
        "usage": "Fallback de transcrição quando a Groq falha ou estoura limite.",
        "format_hint": "Aceita chave OpenAI (sk-...) ou endpoint compatível definido em WHISPER_API_BASE.",
        "remediation": "Cole uma chave OpenAI (sk-...) ou aponte WHISPER_API_BASE para o endpoint compatível (ex.: https://api.groq.com/openai/v1) antes de testar de novo.",
        "test": [
            {
                "url": os.environ.get("WHISPER_API_BASE", "https://api.openai.com/v1").rstrip("/") + "/models",
                "auth": "bearer",
            },
            # Fallback: muitos deploys reaproveitam a Groq como endpoint Whisper.
            {"url": "https://api.groq.com/openai/v1/models", "auth": "bearer"},
        ],
    },
    {
        "id": "tikapi",
        "name": "TikAPI",
        "category": "TikTok",
        "env": "TIKAPI_KEY",
        "docs": "https://tikapi.io/documentation/",
        "usage": "Radar de tendências e metadados de vídeos do TikTok.",
        "remediation": "403 aqui quase sempre é plano expirado ou chave revogada — gere uma nova em tikapi.io → Dashboard → API Key.",
        "test": [
            {
                "url": "https://api.tikapi.io/public/check",
                "auth": "header",
                "header": "X-API-KEY",
                "expect_json": {"status": "success"},
                "invalid_message": "A TikAPI aceitou a requisição mas não confirmou a chave (assinatura inativa).",
            },
            {"url": "https://api.tikapi.io/public/check", "auth": "bearer"},
            {
                "url": "https://api.tikapi.io/public/explore?country=br&count=1",
                "auth": "header",
                "header": "X-API-KEY",
            },
        ],
    },
    {
        "id": "lamatok",
        "name": "Lamatok",
        "category": "TikTok",
        "env": "LAMATOK_API_KEY",
        "docs": "https://api.lamatok.com/docs",
        "usage": "Download direto de mídia do TikTok por URL.",
        "remediation": "402 significa saldo zerado: recarregue créditos em lamatok.com (a chave em si continua válida).",
        "test": [
            {
                "url": "https://api.lamatok.com/v1/user/by/username?username=tiktok",
                "auth": "query",
                "param": "access_key",
            },
            {
                "url": "https://api.lamatok.com/v1/user/by/username?username=tiktok",
                "auth": "header",
                "header": "x-access-key",
            },
        ],
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


def last_test_ok(provider_id: str) -> bool | None:
    """True/False conforme o último teste; None quando nunca foi testado."""
    with _lock:
        stored = _load().get(provider_id, {})
    result = stored.get("last_test")
    if not isinstance(result, dict) or "ok" not in result:
        return None
    return bool(result["ok"])


def rank_providers(provider_ids: list[str]) -> list[str]:
    """Ordena provedores: saudáveis primeiro, não testados depois, falhando por último."""
    order = {True: 0, None: 1, False: 2}
    return sorted(
        [pid for pid in provider_ids if get_key(pid)],
        key=lambda pid: order[last_test_ok(pid)],
    )



def set_key(provider_id: str, key: str, note: str = "") -> dict[str, Any]:
    with _lock:
        data = _load()
        entry = data.get(provider_id, {})
        entry.update({"key": key.strip(), "note": note.strip(), "updated_at": _now()})
        entry.pop("last_test", None)
        data[provider_id] = entry
        _save(data)
        sync_env(data)
    return describe(provider_id)


def delete_key(provider_id: str) -> dict[str, Any]:
    with _lock:
        data = _load()
        data.pop(provider_id, None)
        _save(data)
        sync_env(data)

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
        "format_hint": provider.get("format_hint"),
        "format_ok": (not provider.get("prefix")) or key.startswith(provider["prefix"]) if key else None,
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
_HTTP_MESSAGES = {
    400: "Requisição rejeitada (400) — normalmente formato de credencial errado.",
    401: "Chave inválida ou revogada (401).",
    402: "Créditos esgotados / pagamento pendente (402).",
    403: "Sem permissão para este recurso (403).",
    404: "Endpoint não encontrado (404).",
    429: "Limite de requisições atingido (429).",
}

# Quanto menor, mais informativa é a falha para o usuário.
_FAILURE_RANK = {403: 1, 402: 2, 401: 3, 400: 4, 429: 5, 404: 6, 0: 9}

_ACTION_BY_STATUS = {
    400: "replace_key",
    401: "replace_key",
    402: "billing",
    403: "scope",
    429: "wait",
    0: "network",
}

_DEFAULT_REMEDIATION = {
    "replace_key": "Gere uma nova chave no painel do provedor e cole no campo abaixo.",
    "billing": "A chave é válida, mas a conta está sem créditos — recarregue no provedor.",
    "scope": "A chave existe mas não tem permissão/plano para este recurso. Gere outra com escopo maior.",
    "wait": "Limite de requisições atingido — espere alguns minutos e teste de novo.",
    "network": "O servidor não conseguiu alcançar o provedor. Verifique DNS/firewall do aaPanel.",
}


def _run_probe(spec: dict[str, Any], key: str) -> dict[str, Any]:
    """Executa um único endpoint de verificação e devolve status/ok/mensagem."""
    import base64

    url = spec["url"]
    headers = {"Accept": "application/json", "User-Agent": "EcossistemaViral/1.0"}
    body = None
    method = spec.get("method", "GET")

    for env_name in spec.get("requires_env", []) or []:
        if not os.environ.get(env_name):
            return {
                "ok": None,
                "status": 0,
                "message": f"Defina {env_name} no .env para validar por este método.",
                "skipped": True,
            }
    for header_name, env_name in (spec.get("extra_headers_env") or {}).items():
        value = os.environ.get(env_name, "")
        if value:
            headers[header_name] = value

    auth = spec.get("auth")
    if auth == "bearer":
        headers["Authorization"] = f"Bearer {key}"
    elif auth == "header":
        headers[spec.get("header", "x-api-key")] = key
    elif auth == "query":
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{spec.get('param', 'key')}={urllib.parse.quote(key)}"
    elif auth == "basic":
        user = os.environ.get(spec.get("basic_user_env", ""), "") or spec.get("basic_user", "")
        if not user:
            return {
                "ok": None,
                "status": 0,
                "message": f"Defina {spec.get('basic_user_env')} para validar esta chave.",
            }
        token = base64.b64encode(f"{user}:{key}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"

    if spec.get("body") is not None:
        body = json.dumps(spec["body"]).encode()
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            raw = resp.read(8192)
            # Alguns provedores respondem HTTP 200 com um corpo dizendo que a chave é inválida.
            checks = spec.get("expect_json") or {}
            if checks:
                try:
                    payload = json.loads(raw.decode("utf-8", "replace"))
                except Exception:  # noqa: BLE001
                    payload = None
                if isinstance(payload, dict):
                    for field, expected in checks.items():
                        actual = payload.get(field)
                        if actual != expected:
                            return {
                                "ok": False,
                                "status": resp.status,
                                "message": spec.get("invalid_message")
                                or f"O provedor respondeu 200 mas recusou a chave ({field}={actual!r}).",
                            }
            return {"ok": True, "status": resp.status, "message": "Chave válida e respondendo."}
    except urllib.error.HTTPError as exc:
        status = exc.code
        return {
            "ok": status not in (400, 401, 402, 403, 429),
            "status": status,
            "message": _HTTP_MESSAGES.get(status, f"Endpoint respondeu HTTP {status}."),
        }
    except urllib.error.URLError as exc:
        return {"ok": False, "status": 0, "message": f"Falha de rede: {exc.reason}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": 0, "message": f"Erro inesperado: {exc}"}


def test_provider(provider_id: str) -> dict[str, Any]:
    provider = PROVIDER_BY_ID[provider_id]
    spec = provider.get("test")
    specs = [s for s in (spec if isinstance(spec, list) else [spec]) if s]
    key = get_key(provider_id)
    hint = provider.get("format_hint")

    if not key:
        result = {"ok": False, "status": 0, "message": "Nenhuma chave configurada.", "at": _now()}
        _record_test(provider_id, result)
        return result

    prefix = provider.get("prefix")
    if prefix and not key.startswith(prefix):
        result = {
            "ok": False,
            "status": 0,
            "message": f"Formato inesperado: a chave deveria começar com '{prefix}'."
            + (f" {hint}" if hint else ""),
            "at": _now(),
        }
        _record_test(provider_id, result)
        return result

    if not specs:
        result = {
            "ok": None,
            "status": 0,
            "message": "Provedor sem endpoint de teste — validação manual.",
            "at": _now(),
        }
        _record_test(provider_id, result)
        return result

    started = time.perf_counter()
    attempts: list[dict[str, Any]] = []
    attempt: dict[str, Any] = {}
    for candidate in specs:
        attempt = _run_probe(candidate, key)
        attempts.append(attempt)
        if attempt.get("ok"):
            break

    if not attempt.get("ok"):
        # Mantém a tentativa mais informativa (ignora probes puladas por falta de env).
        real = [a for a in attempts if not a.get("skipped")] or attempts
        attempt = min(real, key=lambda a: _FAILURE_RANK.get(a.get("status", 0), 50))

    message = attempt.get("message", "Falha desconhecida.")
    if attempt.get("ok") is False and hint:
        message = f"{message} {hint}"

    shape = provider.get("shape_warn")
    if attempt.get("ok") is False and shape and re.match(shape["pattern"], key or ""):
        message = f"{message} {shape['message']}"

    action = None
    remediation = None
    if attempt.get("ok") is False:
        action = _ACTION_BY_STATUS.get(attempt.get("status", 0), "check")
        remediation = provider.get("remediation") or _DEFAULT_REMEDIATION.get(action)

    result = {
        "ok": attempt.get("ok"),
        "status": attempt.get("status", 0),
        "message": message,
        "action": action,
        "remediation": remediation,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "at": _now(),
    }
    _record_test(provider_id, result)
    return result



# --- Auto-preenchimento (importação de chaves existentes) --------------------
# Nomes alternativos que o projeto legado usava para a mesma chave.
ALIASES: dict[str, list[str]] = {
    "deepseek": ["DEEPSEEK_KEY", "DEEPSEEK_TOKEN", "DEEP_SEEK_API_KEY"],
    "gemini": ["GOOGLE_API_KEY", "GOOGLE_GEMINI_API_KEY", "GEMINI_KEY"],
    "groq": ["GROQ_KEY", "GROQ_TOKEN"],
    "openrouter": ["OPENROUTER_KEY", "OPEN_ROUTER_API_KEY"],
    "mistral": ["MISTRAL_KEY"],
    "siliconflow": ["SILICON_FLOW_API_KEY", "SILICONFLOW_KEY"],
    "huggingface": ["HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HUGGING_FACE_TOKEN"],
    "cohere": ["COHERE_KEY", "CO_API_KEY"],
    "tavily": ["TAVILY_KEY"],
    "exa": ["EXA_KEY", "EXA_SEARCH_API_KEY"],
    "firecrawl": ["FIRECRAWL_KEY"],
    "jina": ["JINA_TOKEN", "JINA_READER_KEY"],
    "langfuse": ["LANGFUSE_SK", "LANGFUSE_PUBLIC_KEY"],
    "cloudflare": ["CF_API_TOKEN", "CLOUDFLARE_TOKEN"],
    "whisper": ["WHISPER_KEY", "OPENAI_API_KEY"],
    "tikapi": ["TIKAPI_API_KEY", "TIK_API_KEY"],
    "lamatok": ["LAMATOK_KEY", "LAMATOK_TOKEN"],
}

# Assinatura por prefixo — pega a chave mesmo com nome de variável desconhecido.
_PREFIX_OWNER = {
    "gsk_": "groq",
    "sk-or-": "openrouter",
    "tvly-": "tavily",
    "fc-": "firecrawl",
    "hf_": "huggingface",
    "jina_": "jina",
    "sk-lf-": "langfuse",
    "AIza": "gemini",
}


_KV = None  # regex compilada sob demanda
_autofill_done = False



_SCAN_EXT = {".env", ".json", ".py", ".txt", ".ini", ".cfg", ".conf", ".yaml", ".yml", ".sh", ".md"}
_SKIP_DIRS = {
    "node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", ".cache", "site-packages", "fabrica_clips", "_canva_jobs", ".bun",
}
_MAX_DEPTH = 4
_MAX_FILE_BYTES = 2_000_000


def _scan_roots() -> list:
    """Diretórios onde as chaves podem estar (app atual, app legado, extras)."""
    from pathlib import Path

    extra = os.environ.get("VIRAL_KEY_SCAN_PATHS", "")
    roots = [
        config.app_root,
        config.storage_dir / "_config",
        Path("/www/wwwroot/viral.vr766.com"),
        Path("/www/wwwroot/viral.vr766.com.bak"),
        Path("/www/wwwroot/viral"),
        Path("/root"),
    ]
    roots += [Path(p) for p in extra.split(":") if p.strip()]
    seen, out = set(), []
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        try:
            if root.exists():
                out.append(root)
        except OSError:
            continue
    return out


def _scan_paths() -> list:
    """Varredura recursiva (profundidade limitada) por arquivos de configuração."""
    from pathlib import Path

    found: list[Path] = []
    for root in _scan_roots():
        base_depth = len(root.parts)
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                current = Path(dirpath)
                if len(current.parts) - base_depth >= _MAX_DEPTH:
                    dirnames[:] = []
                dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".git")]
                for name in filenames:
                    lowered = name.lower()
                    if not (lowered.startswith(".env") or lowered.startswith("env")
                            or Path(lowered).suffix in _SCAN_EXT):
                        continue
                    f = current / name
                    try:
                        if f.is_file() and f.stat().st_size < _MAX_FILE_BYTES:
                            found.append(f)
                    except OSError:
                        continue
                if len(found) > 4000:
                    return found
        except OSError:
            continue
    return found


def _harvest(text: str) -> dict[str, str]:
    """Extrai pares NOME=valor / "nome": "valor" de qualquer formato texto."""
    global _KV
    import re

    if _KV is None:
        _KV = re.compile(
            r'["\']?([A-Za-z_][A-Za-z0-9_]{2,60})["\']?\s*[:=]\s*["\']?'
            r'([A-Za-z0-9_\-\.]{12,200})["\']?'
        )
    out: dict[str, str] = {}
    for name, value in _KV.findall(text):
        upper = name.upper()
        if value.lower() in {"none", "null", "true", "false", "change-me-in-env"}:
            continue
        out.setdefault(upper, value)
    return out


def _harvest_signatures(text: str) -> dict[str, str]:
    """Captura chaves pelo formato do valor, mesmo sem nome de variável."""
    import re

    out: dict[str, str] = {}
    for prefix, owner in _PREFIX_OWNER.items():
        pattern = re.escape(prefix) + r"[A-Za-z0-9_\-]{16,200}"
        match = re.search(pattern, text)
        if match:
            out.setdefault(owner, match.group(0))
    # Gemini/Google: AIza...
    match = re.search(r"AIza[A-Za-z0-9_\-]{30,60}", text)
    if match:
        out.setdefault("gemini", match.group(0))
    return out


def scan_report() -> dict[str, Any]:
    """Diagnóstico: o que a varredura enxerga hoje (sem expor as chaves)."""
    harvested, sources = _collect()
    hits = []
    for provider in PROVIDERS:
        pid = provider["id"]
        candidates = [provider["env"]] + ALIASES.get(pid, [])
        name = next((c.upper() for c in candidates if harvested.get(c.upper())), None)
        if not name and harvested.get(f"__SIG__{pid}"):
            name = "assinatura do valor"
        hits.append({
            "id": pid,
            "name": provider["name"],
            "found": bool(name),
            "var": name,
            "origin": sources.get(name or "", "") if name else "",
        })
    files = [str(p) for p in _scan_paths()]
    return {
        "roots": [str(r) for r in _scan_roots()],
        "files_scanned": len(files),
        "files": files[:120],
        "env_vars_seen": len([k for k, v in os.environ.items() if v and len(v) >= 12]),
        "hits": hits,
    }


# Catálogo legado (TODASAPI.txt): blocos "N - NOME" seguidos das chaves soltas.
_LEGACY_TITLES = {
    "deepseek": "deepseek",
    "gemini": "gemini",
    "google gemini": "gemini",
    "groq": "groq",
    "cohere api": "cohere",
    "cohere": "cohere",
    "tavily": "tavily",
    "jina": "jina",
    "openrouter": "openrouter",
    "open router": "openrouter",
    "mistral": "mistral",
    "huggingface": "huggingface",
    "hugging face": "huggingface",
    "cloudflare api workers": "cloudflare",
    "cloudflare": "cloudflare",
    "firecrawl": "firecrawl",
    "exa": "exa",
    "langfuse": "langfuse",
    "siliconflow": "siliconflow",
    "whisper": "whisper",
    "lamatok": "lamatok",
    "tikapi": "tikapi",
}

_LEGACY_NOISE = {
    "chave", "teste", "producao", "produção", "documentacao", "documentação",
    "id", "api", "key", "token", "http", "https", "none", "null",
}


def _parse_legacy_catalog(text: str) -> dict[str, str]:
    """Lê o formato do TODASAPI.txt do projeto legado (sem NOME=valor)."""
    import re

    if "======" not in text or not re.search(r"^\s*\d+\s*-", text, re.M):
        return {}

    out: dict[str, str] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        header = re.match(r"^\d+\s*-\s*(.+)$", line)
        if header:
            title = re.sub(r"\s+", " ", header.group(1)).strip().lower()
            current = _LEGACY_TITLES.get(title)
            if current is None:
                current = next(
                    (pid for name, pid in _LEGACY_TITLES.items() if name in title),
                    None,
                )
            continue
        if not current or current in out:
            continue
        if line.startswith("=") or line.startswith("#") or "://" in line:
            continue
        candidate = line.split()[-1].strip("\"',;")
        if candidate.upper().startswith(("ID", "CHAVE")):
            continue
        if len(candidate) < 16 or candidate.lower() in _LEGACY_NOISE:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_\-\.:]{16,300}", candidate):
            continue
        out[current] = candidate
    return out


_ALT_CANDIDATES: dict[str, list[tuple[str, str]]] = {}


def _collect() -> tuple[dict[str, str], dict[str, str]]:
    harvested: dict[str, str] = {}
    sources: dict[str, str] = {}
    alts: dict[str, list[tuple[str, str]]] = {}

    def remember(pid: str, value: str, origin: str) -> None:
        bucket = alts.setdefault(pid, [])
        if value not in [v for v, _ in bucket]:
            bucket.append((value, origin))

    for key, value in os.environ.items():
        if value and len(value) >= 12:
            harvested.setdefault(key.upper(), value)
            sources.setdefault(key.upper(), "ambiente")

    for path in _scan_paths():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, value in _harvest(text).items():
            if name not in harvested:
                harvested[name] = value
                sources[name] = str(path)
        for pid, value in _parse_legacy_catalog(text).items():
            marker = f"__SIG__{pid}"
            remember(pid, value, f"{path} (catálogo legado)")
            if marker not in harvested:
                harvested[marker] = value
                sources[marker] = f"{path} (catálogo legado)"
        for pid, value in _harvest_signatures(text).items():
            marker = f"__SIG__{pid}"
            remember(pid, value, str(path))
            if marker not in harvested:
                harvested[marker] = value
                sources[marker] = str(path)

    _ALT_CANDIDATES.clear()
    _ALT_CANDIDATES.update(alts)
    return harvested, sources



def sync_env(data: dict[str, dict[str, Any]] | None = None) -> str | None:
    """Espelha o cofre no .env da aplicação (0600), preservando as demais variáveis."""
    entries = data if data is not None else _load()
    env_path = config.app_root / ".env"
    managed = {p["env"]: (entries.get(p["id"]) or {}).get("key") for p in PROVIDERS}
    managed = {name: key for name, key in managed.items() if key}

    lines: list[str] = []
    try:
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        lines = []

    out: list[str] = []
    written: set[str] = set()
    for line in lines:
        name = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if name in managed:
            out.append(f"{name}={managed[name]}")
            written.add(name)
        else:
            out.append(line)

    pending = [f"{n}={v}" for n, v in managed.items() if n not in written]
    if pending:
        if out and out[-1].strip():
            out.append("")
        out.append("# --- Central de APIs (gerado automaticamente) ---")
        out.extend(pending)

    try:
        env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
        os.chmod(env_path, 0o600)
    except OSError:
        return None
    return str(env_path)



def autofill(force: bool = False) -> dict[str, Any]:
    """Preenche o cofre com chaves encontradas no ambiente e em arquivos legados."""
    harvested, sources = _collect()

    with _lock:
        data = _load()
        imported, skipped = [], []

        for provider in PROVIDERS:
            pid = provider["id"]
            existing = (data.get(pid) or {}).get("key")
            if existing and not force:
                skipped.append(pid)
                continue

            candidates = [provider["env"]] + ALIASES.get(pid, [])
            value = next((harvested[c.upper()] for c in candidates if harvested.get(c.upper())), None)
            origin = next((sources[c.upper()] for c in candidates if harvested.get(c.upper())), "")

            from_catalog = False
            if not value:
                marker = f"__SIG__{pid}"
                if harvested.get(marker):
                    value, origin = harvested[marker], sources.get(marker, "")
                    from_catalog = True

            if not value:
                continue
            prefix = provider.get("prefix")
            if prefix and not value.startswith(prefix):
                # nunca importa credencial com formato incompatível (ex.: token OAuth
                # "AQ." caindo no slot do Gemini, que exige "AIza")
                continue

            # Quando o legado tem mais de uma chave para o mesmo provedor (ex.: Lamatok
            # com uma chave sem saldo e outra ativa), testa de verdade e importa a que passa.
            pool = [(value, origin)] + [
                (alt, src)
                for alt, src in _ALT_CANDIDATES.get(pid, [])
                if alt != value and (not prefix or alt.startswith(prefix))
            ]
            if len(pool) > 1:
                for candidate_key, candidate_origin in pool:
                    if _probe_key(provider, candidate_key):
                        value, origin = candidate_key, candidate_origin
                        break




            entry = data.get(pid, {})
            entry.update({
                "key": value.strip(),
                "note": entry.get("note") or f"Importado automaticamente de {origin or 'ambiente'}",
                "updated_at": _now(),
            })
            entry.pop("last_test", None)
            data[pid] = entry
            imported.append(pid)

        if imported:
            _save(data)
        env_file = sync_env(data)

    return {
        "imported": imported,
        "skipped": skipped,
        "scanned": len(_scan_paths()),
        "roots": [str(r) for r in _scan_roots()],
        "env_file": env_file,
        "total_configured": sum(1 for p in list_all() if p["configured"]),
    }



def autofill_once() -> None:
    """Roda uma vez por processo, no boot da aplicação."""
    global _autofill_done
    if _autofill_done:
        return
    _autofill_done = True
    try:
        autofill(force=False)
    except Exception:  # noqa: BLE001 — nunca derruba o boot
        pass
