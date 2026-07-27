/**
 * Laboratório de APIs — catálogo de chamadas REAIS.
 *
 * Este módulo é client-safe: descreve *como* montar cada requisição, sem
 * nenhuma chave embutida. A execução acontece só no servidor
 * (`api-lab.functions.ts`), o que evita CORS e mantém a chave fora do bundle.
 */

export type LabField = {
  name: string;
  label: string;
  placeholder?: string;
  defaultValue?: string;
  multiline?: boolean;
};

export type LabRequest = {
  method: string;
  url: string;
  headers: Record<string, string>;
  /** JSON serializado, texto puro, ou null. */
  body?: string | null;
  /** Quando true, o servidor monta um multipart com um WAV mínimo de silêncio. */
  audioProbe?: boolean;
  /** Campos extras do multipart (model, response_format...). */
  audioFields?: Record<string, string>;
};

export type LabPreset = {
  id: string;
  group: string;
  label: string;
  /** O que essa chamada realmente devolve, em português claro. */
  expects: string;
  keyLabel: string;
  keyHint?: string;
  docs?: string;
  fields?: LabField[];
  build: (key: string, values: Record<string, string>) => LabRequest;
};

const json = (key: string, scheme = "Bearer") => ({
  "Content-Type": "application/json",
  Authorization: `${scheme} ${key}`,
});

export const LAB_PRESETS: LabPreset[] = [
  // ---------------------------------------------------------------- Groq
  {
    id: "groq.models",
    group: "Groq",
    label: "Groq · listar modelos",
    expects:
      "Lista de modelos liberados para a chave. Serve para saber se a chave é válida, mas NÃO prova acesso ao Whisper.",
    keyLabel: "GROQ_API_KEY",
    keyHint: "gsk_...",
    docs: "https://console.groq.com/keys",
    build: (key) => ({
      method: "GET",
      url: "https://api.groq.com/openai/v1/models",
      headers: { Authorization: `Bearer ${key}` },
    }),
  },
  {
    id: "groq.transcribe",
    group: "Groq",
    label: "Groq · transcrição Whisper (o que a Dublagem usa)",
    expects:
      "Envia 0,3 s de silêncio para /audio/transcriptions. 200 = a dublagem consegue ouvir o vídeo. 403 = plano sem Whisper. 401 = chave inválida.",
    keyLabel: "GROQ_API_KEY",
    keyHint: "gsk_...",
    fields: [
      { name: "model", label: "Modelo", defaultValue: "whisper-large-v3", placeholder: "whisper-large-v3" },
    ],
    build: (key, v) => ({
      method: "POST",
      url: "https://api.groq.com/openai/v1/audio/transcriptions",
      headers: { Authorization: `Bearer ${key}` },
      audioProbe: true,
      audioFields: { model: v.model || "whisper-large-v3", response_format: "json" },
    }),
  },
  {
    id: "groq.chat",
    group: "Groq",
    label: "Groq · chat completions",
    expects: "Resposta de texto do LLM. Mostra o formato exato (choices[0].message.content) e o uso de tokens.",
    keyLabel: "GROQ_API_KEY",
    fields: [
      { name: "model", label: "Modelo", defaultValue: "llama-3.3-70b-versatile" },
      { name: "prompt", label: "Prompt", defaultValue: "Responda apenas: ok", multiline: true },
    ],
    build: (key, v) => ({
      method: "POST",
      url: "https://api.groq.com/openai/v1/chat/completions",
      headers: json(key),
      body: JSON.stringify({
        model: v.model || "llama-3.3-70b-versatile",
        messages: [{ role: "user", content: v.prompt || "Responda apenas: ok" }],
        max_tokens: 64,
      }),
    }),
  },

  // ------------------------------------------------------- OpenAI/Whisper
  {
    id: "openai.transcribe",
    group: "OpenAI / Whisper",
    label: "OpenAI · transcrição (fallback da dublagem)",
    expects:
      "Mesmo probe de áudio no endpoint OpenAI. É o fallback do transcribe.py quando a Groq falha.",
    keyLabel: "WHISPER_API_KEY / OPENAI_API_KEY",
    keyHint: "sk-...",
    fields: [
      { name: "base", label: "Base URL", defaultValue: "https://api.openai.com/v1" },
      { name: "model", label: "Modelo", defaultValue: "whisper-1" },
    ],
    build: (key, v) => ({
      method: "POST",
      url: `${(v.base || "https://api.openai.com/v1").replace(/\/$/, "")}/audio/transcriptions`,
      headers: { Authorization: `Bearer ${key}` },
      audioProbe: true,
      audioFields: { model: v.model || "whisper-1", response_format: "json" },
    }),
  },
  {
    id: "openai.models",
    group: "OpenAI / Whisper",
    label: "OpenAI · listar modelos",
    expects: "Confirma se a chave existe e quais modelos ela enxerga.",
    keyLabel: "OPENAI_API_KEY",
    fields: [{ name: "base", label: "Base URL", defaultValue: "https://api.openai.com/v1" }],
    build: (key, v) => ({
      method: "GET",
      url: `${(v.base || "https://api.openai.com/v1").replace(/\/$/, "")}/models`,
      headers: { Authorization: `Bearer ${key}` },
    }),
  },

  // ------------------------------------------------------------ ElevenLabs
  {
    id: "elevenlabs.user",
    group: "ElevenLabs",
    label: "ElevenLabs · assinatura e créditos",
    expects: "Quantidade de caracteres restantes no plano — é o teto real da narração.",
    keyLabel: "ELEVENLABS_API_KEY",
    keyHint: "sk_...",
    build: (key) => ({
      method: "GET",
      url: "https://api.elevenlabs.io/v1/user/subscription",
      headers: { "xi-api-key": key },
    }),
  },
  {
    id: "elevenlabs.voices",
    group: "ElevenLabs",
    label: "ElevenLabs · vozes disponíveis",
    expects: "IDs de voz reais (voice_id) que o backend precisa usar no TTS.",
    keyLabel: "ELEVENLABS_API_KEY",
    build: (key) => ({
      method: "GET",
      url: "https://api.elevenlabs.io/v1/voices",
      headers: { "xi-api-key": key },
    }),
  },

  // ----------------------------------------------------------------- LLMs
  {
    id: "deepseek.chat",
    group: "LLMs",
    label: "DeepSeek · chat completions",
    expects: "Resposta do modelo DeepSeek no formato OpenAI.",
    keyLabel: "DEEPSEEK_API_KEY",
    fields: [
      { name: "model", label: "Modelo", defaultValue: "deepseek-chat" },
      { name: "prompt", label: "Prompt", defaultValue: "Responda apenas: ok", multiline: true },
    ],
    build: (key, v) => ({
      method: "POST",
      url: "https://api.deepseek.com/chat/completions",
      headers: json(key),
      body: JSON.stringify({
        model: v.model || "deepseek-chat",
        messages: [{ role: "user", content: v.prompt || "Responda apenas: ok" }],
        max_tokens: 64,
      }),
    }),
  },
  {
    id: "openrouter.chat",
    group: "LLMs",
    label: "OpenRouter · chat completions",
    expects: "Resposta agregada de qualquer modelo do OpenRouter.",
    keyLabel: "OPENROUTER_API_KEY",
    fields: [
      { name: "model", label: "Modelo", defaultValue: "meta-llama/llama-3.3-70b-instruct" },
      { name: "prompt", label: "Prompt", defaultValue: "Responda apenas: ok", multiline: true },
    ],
    build: (key, v) => ({
      method: "POST",
      url: "https://openrouter.ai/api/v1/chat/completions",
      headers: json(key),
      body: JSON.stringify({
        model: v.model || "meta-llama/llama-3.3-70b-instruct",
        messages: [{ role: "user", content: v.prompt || "Responda apenas: ok" }],
        max_tokens: 64,
      }),
    }),
  },
  {
    id: "gemini.generate",
    group: "LLMs",
    label: "Gemini · generateContent",
    expects: "Texto gerado pelo Gemini. A chave vai na query string (?key=), não no header.",
    keyLabel: "GEMINI_API_KEY",
    keyHint: "AIza...",
    fields: [
      { name: "model", label: "Modelo", defaultValue: "gemini-2.0-flash" },
      { name: "prompt", label: "Prompt", defaultValue: "Responda apenas: ok", multiline: true },
    ],
    build: (key, v) => ({
      method: "POST",
      url: `https://generativelanguage.googleapis.com/v1beta/models/${
        v.model || "gemini-2.0-flash"
      }:generateContent?key=${encodeURIComponent(key)}`,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: v.prompt || "Responda apenas: ok" }] }],
      }),
    }),
  },
  {
    id: "cohere.chat",
    group: "LLMs",
    label: "Cohere · chat v2",
    expects: "Resposta do Command R no formato message.content[].text.",
    keyLabel: "COHERE_API_KEY",
    fields: [
      { name: "model", label: "Modelo", defaultValue: "command-r-plus" },
      { name: "prompt", label: "Prompt", defaultValue: "Responda apenas: ok", multiline: true },
    ],
    build: (key, v) => ({
      method: "POST",
      url: "https://api.cohere.com/v2/chat",
      headers: json(key),
      body: JSON.stringify({
        model: v.model || "command-r-plus",
        messages: [{ role: "user", content: v.prompt || "Responda apenas: ok" }],
      }),
    }),
  },
  {
    id: "mistral.chat",
    group: "LLMs",
    label: "Mistral · chat completions",
    expects: "Resposta do Mistral no formato OpenAI.",
    keyLabel: "MISTRAL_API_KEY",
    fields: [
      { name: "model", label: "Modelo", defaultValue: "mistral-small-latest" },
      { name: "prompt", label: "Prompt", defaultValue: "Responda apenas: ok", multiline: true },
    ],
    build: (key, v) => ({
      method: "POST",
      url: "https://api.mistral.ai/v1/chat/completions",
      headers: json(key),
      body: JSON.stringify({
        model: v.model || "mistral-small-latest",
        messages: [{ role: "user", content: v.prompt || "Responda apenas: ok" }],
        max_tokens: 64,
      }),
    }),
  },

  // --------------------------------------------------------- Web / dados
  {
    id: "tavily.search",
    group: "Pesquisa e extração",
    label: "Tavily · search",
    expects: "Resultados de busca com título, url e snippet — insumo do Radar Global.",
    keyLabel: "TAVILY_API_KEY",
    keyHint: "tvly-...",
    fields: [{ name: "query", label: "Consulta", defaultValue: "tendências virais tiktok" }],
    build: (key, v) => ({
      method: "POST",
      url: "https://api.tavily.com/search",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: key,
        query: v.query || "tendências virais tiktok",
        max_results: 3,
      }),
    }),
  },
  {
    id: "exa.search",
    group: "Pesquisa e extração",
    label: "Exa · search",
    expects: "Resultados semânticos da Exa (results[].url/title).",
    keyLabel: "EXA_API_KEY",
    fields: [{ name: "query", label: "Consulta", defaultValue: "viral video trends 2026" }],
    build: (key, v) => ({
      method: "POST",
      url: "https://api.exa.ai/search",
      headers: { "Content-Type": "application/json", "x-api-key": key },
      body: JSON.stringify({ query: v.query || "viral video trends 2026", numResults: 3 }),
    }),
  },
  {
    id: "firecrawl.scrape",
    group: "Pesquisa e extração",
    label: "Firecrawl · scrape",
    expects: "Markdown limpo da página pedida.",
    keyLabel: "FIRECRAWL_API_KEY",
    keyHint: "fc-...",
    fields: [{ name: "url", label: "URL", defaultValue: "https://example.com" }],
    build: (key, v) => ({
      method: "POST",
      url: "https://api.firecrawl.dev/v1/scrape",
      headers: json(key),
      body: JSON.stringify({ url: v.url || "https://example.com", formats: ["markdown"] }),
    }),
  },
  {
    id: "jina.reader",
    group: "Pesquisa e extração",
    label: "Jina Reader · r.jina.ai",
    expects: "Texto puro da página, pronto para o LLM ler.",
    keyLabel: "JINA_API_KEY",
    keyHint: "jina_...",
    fields: [{ name: "url", label: "URL", defaultValue: "https://example.com" }],
    build: (key, v) => ({
      method: "GET",
      url: `https://r.jina.ai/${v.url || "https://example.com"}`,
      headers: { Authorization: `Bearer ${key}` },
    }),
  },

  // ------------------------------------------------------------- TikTok
  {
    id: "tikapi.check",
    group: "TikTok",
    label: "TikAPI · verificar chave",
    expects: "Status da conta TikAPI e limites de uso.",
    keyLabel: "TIKAPI_KEY",
    build: (key) => ({
      method: "GET",
      url: "https://api.tikapi.io/user/info?username=tiktok",
      headers: { "X-API-KEY": key },
    }),
  },

  // -------------------------------------------------------------- Custom
  {
    id: "custom",
    group: "Livre",
    label: "Requisição livre (qualquer endpoint)",
    expects: "Você define método, URL, headers e corpo. Útil para provar um endpoint novo antes de codar.",
    keyLabel: "Chave (opcional — use {{key}} nos headers)",
    fields: [
      { name: "method", label: "Método", defaultValue: "GET" },
      { name: "url", label: "URL", defaultValue: "https://api.exemplo.com/v1/ping" },
      {
        name: "headers",
        label: "Headers (JSON)",
        defaultValue: '{"Authorization": "Bearer {{key}}"}',
        multiline: true,
      },
      { name: "body", label: "Body (texto ou JSON)", defaultValue: "", multiline: true },
    ],
    build: (key, v) => {
      let headers: Record<string, string> = {};
      try {
        const raw = (v.headers || "{}").replaceAll("{{key}}", key);
        const parsed = JSON.parse(raw) as Record<string, unknown>;
        headers = Object.fromEntries(Object.entries(parsed).map(([k, val]) => [k, String(val)]));
      } catch {
        headers = key ? { Authorization: `Bearer ${key}` } : {};
      }
      return {
        method: (v.method || "GET").toUpperCase(),
        url: v.url || "",
        headers,
        body: v.body ? v.body.replaceAll("{{key}}", key) : null,
      };
    },
  },
];

export const LAB_GROUPS = Array.from(new Set(LAB_PRESETS.map((p) => p.group)));

export function findPreset(id: string): LabPreset | undefined {
  return LAB_PRESETS.find((p) => p.id === id);
}
