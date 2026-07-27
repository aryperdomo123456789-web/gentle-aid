/**
 * Cliente HTTP do Ecossistema Viral.
 *
 * Em produção (aaPanel/Nginx) o frontend é servido no mesmo domínio do Flask,
 * então BASE = "" e todas as chamadas são relativas (`/api/...`) — sem CORS.
 * Em desenvolvimento, defina VITE_API_BASE=http://127.0.0.1:8000 no .env.
 *
 * Esta é a única camada do app que fala `fetch`. Toda feature consome as
 * funções daqui através do seu próprio módulo `features/<dominio>/api.ts`.
 */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

/** Tempo máximo de espera de um GET antes de considerar o backend fora do ar. */
const GET_TIMEOUT_MS = 25_000;

export type ApiError = { status: number; message: string };

export class ViralApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ViralApiError";
  }
}

const JSON_HEADERS = { "Content-Type": "application/json", Accept: "application/json" } as const;
const ACCEPT_JSON = { Accept: "application/json" } as const;

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const payload = data as { error?: string; message?: string } | null;
    const message =
      payload?.error ??
      payload?.message ??
      (res.status === 404
        ? "Rota não encontrada. Verifique se o backend Flask está rodando no servidor."
        : `Falha na requisição (HTTP ${res.status}).`);
    throw new ViralApiError(res.status, message);
  }

  return data as T;
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include", ...init });
  return parse<T>(res);
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), GET_TIMEOUT_MS);
  if (signal) signal.addEventListener("abort", () => ctrl.abort(), { once: true });
  try {
    return await request<T>(path, { method: "GET", headers: ACCEPT_JSON, signal: ctrl.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ViralApiError(
        504,
        "O backend não respondeu em 25s. Verifique se o serviço viral-api está ativo e se o Nginx faz proxy de /api para a porta do Gunicorn.",
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) });
}

export function apiPutJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(body) });
}

export function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, { method: "POST", headers: ACCEPT_JSON, body: form });
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE", headers: ACCEPT_JSON });
}

/** Monta uma query string ignorando valores vazios/indefinidos. */
export function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

/** Resolve um caminho servido pelo Nginx em URL absoluta de download. */
export function downloadUrl(path: string): string {
  if (!path) return "#";
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Converte qualquer erro em uma mensagem legível para o operador. */
export function friendlyError(err: unknown): string {
  if (err instanceof ViralApiError) return err.message;
  if (err instanceof TypeError)
    return "Não foi possível falar com o servidor. Confirme que o serviço Flask está ativo atrás do Nginx.";
  if (err instanceof Error) return err.message;
  return "Erro inesperado.";
}
