/**
 * Cliente HTTP do Ecossistema Viral.
 *
 * Em produção (aaPanel/Nginx) o frontend é servido no mesmo domínio do Flask,
 * então BASE = "" e todas as chamadas são relativas (`/api/...`) — sem CORS.
 * Em desenvolvimento, defina VITE_API_BASE=http://127.0.0.1:8000 no .env.
 */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";

export type ApiError = { status: number; message: string };

export class ViralApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ViralApiError";
  }
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const message =
      (data as { error?: string; message?: string } | null)?.error ??
      (data as { error?: string; message?: string } | null)?.message ??
      (res.status === 404
        ? "Rota não encontrada. Verifique se o backend Flask está rodando no servidor."
        : `Falha na requisição (HTTP ${res.status}).`);
    throw new ViralApiError(res.status, message);
  }

  return data as T;
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  return parse<T>(res);
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  return parse<T>(res);
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: form,
  });
  return parse<T>(res);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });
  return parse<T>(res);
}



export function downloadUrl(path: string): string {
  if (!path) return "#";
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

export function friendlyError(err: unknown): string {
  if (err instanceof ViralApiError) return err.message;
  if (err instanceof TypeError)
    return "Não foi possível falar com o servidor. Confirme que o serviço Flask está ativo (porta 8000) atrás do Nginx.";
  if (err instanceof Error) return err.message;
  return "Erro inesperado.";
}

/** Status normalizado de um job de processamento. */
export type JobStatus = "queued" | "running" | "done" | "error";

/** Relatório de esterilização devolvido pelo backend. */
export type SterilizationReport = {
  level: string;
  seed: number;
  md5_before: string;
  md5_after: string;
  sha256_after: string;
  bitrate: string;
  attempts: number;
  video_filters: string[];
  audio_filters: string[];
  identity: Record<string, string>;
  steps: string[];
  unique: boolean;
};

export type JobOutput = {
  url?: string;
  download_url: string;
  filename: string;
  md5_before?: string;
  md5_after?: string;
};

export type Job = {
  job_id: string;
  tool: string;
  status: JobStatus;
  message?: string;
  progress?: number;
  created_at?: string;
  finished_at?: string;
  download_url?: string | null;
  filename?: string | null;
  size_bytes?: number;
  md5_before?: string | null;
  md5_after?: string | null;
  sha256_after?: string | null;
  sterilization?: SterilizationReport | null;
  outputs?: JobOutput[];
  log?: string[];
  meta?: Record<string, unknown>;
};

