/**
 * Execução real das chamadas do Laboratório de APIs (somente servidor).
 *
 * Roda no runtime do Lovable — por isso funciona aqui mesmo sem o Flask do
 * aaPanel no ar. Nenhuma chave é gravada em disco: ela chega na requisição,
 * é usada uma vez e descartada.
 */
import { findPreset, type LabRequest } from "./api-lab.presets";

export type LabResult = {
  ok: boolean;
  status: number;
  statusText: string;
  durationMs: number;
  url: string;
  method: string;
  requestHeaders: string[];
  responseHeaders: Record<string, string>;
  contentType: string;
  bodyPreview: string;
  bodyBytes: number;
  truncated: boolean;
  verdict: string;
  error?: string;
};

const MAX_PREVIEW = 20_000;

/** WAV PCM 16-bit mono, 0,3 s de silêncio — o mesmo probe usado no backend. */
export function tinyWav(): Uint8Array {
  const sampleRate = 16_000;
  const samples = Math.round(sampleRate * 0.3);
  const dataSize = samples * 2;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);
  const ascii = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i += 1) view.setUint8(offset + i, text.charCodeAt(i));
  };
  ascii(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  ascii(8, "WAVEfmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  ascii(36, "data");
  view.setUint32(40, dataSize, true);
  return new Uint8Array(buffer);
}

function verdictFor(status: number, body: string): string {
  if (status === 401)
    return "401 — chave inválida, revogada ou no header errado. Gere outra no painel do provedor.";
  if (status === 403)
    return "403 — a chave existe mas o plano/organização não libera este endpoint (caso clássico da Groq sem Whisper).";
  if (status === 404) return "404 — endpoint ou modelo inexistente. Confira URL e nome do modelo.";
  if (status === 422 || status === 400)
    return "400/422 — a chamada chegou autenticada, mas o corpo está fora do formato esperado.";
  if (status === 429) return "429 — limite de requisições ou créditos esgotados.";
  if (status >= 500) return "5xx — falha do lado do provedor; tente de novo antes de trocar a chave.";
  if (status >= 200 && status < 300)
    return body.trim()
      ? "200 — resposta real recebida. É exatamente isso que o backend vai receber."
      : "200 — resposta vazia, mas autenticada.";
  return `HTTP ${status}.`;
}

async function buildInit(req: LabRequest): Promise<RequestInit> {
  if (req.audioProbe) {
    const form = new FormData();
    for (const [k, v] of Object.entries(req.audioFields ?? {})) form.append(k, v);
    const bytes = tinyWav();
    form.append("file", new Blob([bytes as unknown as BlobPart], { type: "audio/wav" }), "probe.wav");
    return { method: req.method, headers: req.headers, body: form };
  }
  return {
    method: req.method,
    headers: req.headers,
    body: req.method === "GET" || req.method === "HEAD" ? undefined : (req.body ?? undefined),
  };
}

export async function runLabRequest(input: {
  presetId: string;
  key: string;
  values: Record<string, string>;
}): Promise<LabResult> {
  const preset = findPreset(input.presetId);
  if (!preset) throw new Error("Preset desconhecido.");

  const req = preset.build(input.key.trim(), input.values ?? {});
  if (!/^https?:\/\//i.test(req.url)) throw new Error("URL inválida — use http(s)://");

  const started = Date.now();
  const init = await buildInit(req);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45_000);

  const base: Omit<LabResult, "status" | "statusText" | "ok" | "responseHeaders" | "contentType" | "bodyPreview" | "bodyBytes" | "truncated" | "verdict"> =
    {
      durationMs: 0,
      url: req.url.replace(/key=[^&]+/i, "key=***"),
      method: req.method,
      requestHeaders: Object.keys(req.headers),
    };

  try {
    const res = await fetch(req.url, { ...init, signal: controller.signal });
    const text = await res.text();
    const preview = text.length > MAX_PREVIEW ? text.slice(0, MAX_PREVIEW) : text;
    return {
      ...base,
      durationMs: Date.now() - started,
      ok: res.ok,
      status: res.status,
      statusText: res.statusText,
      responseHeaders: Object.fromEntries(
        Array.from(res.headers.entries()).filter(
          ([k]) => !/^set-cookie$/i.test(k) && !/authorization/i.test(k),
        ),
      ),
      contentType: res.headers.get("content-type") ?? "",
      bodyPreview: preview,
      bodyBytes: text.length,
      truncated: text.length > MAX_PREVIEW,
      verdict: verdictFor(res.status, text),
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      ...base,
      durationMs: Date.now() - started,
      ok: false,
      status: 0,
      statusText: "sem resposta",
      responseHeaders: {},
      contentType: "",
      bodyPreview: "",
      bodyBytes: 0,
      truncated: false,
      verdict:
        message.includes("abort")
          ? "Tempo esgotado (45 s) — o provedor não respondeu."
          : "Falha de rede antes de chegar ao provedor.",
      error: message,
    };
  } finally {
    clearTimeout(timer);
  }
}
