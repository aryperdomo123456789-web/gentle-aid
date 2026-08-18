/** Tipos de domínio dos jobs de processamento (FFmpeg / esterilização). */

/** Status normalizado de um job de processamento. */
export type JobStatus = "queued" | "running" | "done" | "error" | "cancelled";

/** Ferramentas do ecossistema que geram jobs. */
export type ToolId = "youtube" | "tiktok" | "legendar" | "transcribe" | "voice" | "canva" | "studio";

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
  source_width?: number;
  source_height?: number;
  source_orientation?: "portrait" | "landscape" | "square" | "unknown";
  source_aspect_ratio?: number;
  source_duration?: number;
  source_bitrate?: number;
  source_size_bytes?: number;
  source_video_codec?: string;
  output_duration?: number;
  output_bitrate?: number;
  output_size_bytes?: number;
  output_video_codec?: string;
  audit_summary?: string;
};

export type JobOutput = {
  url?: string;
  download_url: string;
  filename: string;
  md5_before?: string;
  md5_after?: string;
};

/** Evento estruturado do rastro do job (mesmo padrão em todas as ferramentas). */
export type JobEventLevel = "lifecycle" | "stage" | "info" | "audit" | "artifact" | "error";

export type JobEvent = {
  ts: string;
  level: JobEventLevel | string;
  stage: string;
  message: string;
};

/** Linha da trilha de auditoria append-only (sobrevive à exclusão do job). */
export type JobAuditEntry = {
  ts: string;
  action: string;
  job_id: string;
  tool?: string;
  detail?: string;
};

export type JobTrace = {
  job_id: string;
  status?: JobStatus;
  stage?: string | null;
  events: JobEvent[];
  log: string[];
  artifacts: { path: string; kind: string }[];
  audit: JobAuditEntry[];
};

/** Estatísticas agregadas devolvidas pela Central de Jobs. */
export type JobToolStats = {
  total: number;
  done: number;
  error: number;
  cancelled: number;
  running: number;
  bytes: number;
};

export type JobStats = JobToolStats & {
  total_all?: number;
  by_tool?: Record<string, JobToolStats>;
};

export type Job = {
  job_id: string;
  tool: string;
  tool_label?: string;
  stage?: string | null;
  updated_at?: string;
  duration_ms?: number | null;
  terminal?: boolean;
  events?: JobEvent[];
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
  audit_summary?: string | null;
  sterilization?: SterilizationReport | null;
  outputs?: JobOutput[];
  artifacts?: { path: string; kind: string }[];
  source_kind?: "upload" | "download" | null;
  source_label?: string | null;
  source_path?: string | null;
  source_url?: string | null;
  transcript_text?: string | null;
  transcript_language?: string | null;
  log?: string[];
  meta?: Record<string, unknown>;
};

/** Um job terminou quando não há mais transições possíveis. */
export function isTerminalStatus(status: JobStatus): boolean {
  return status === "done" || status === "error" || status === "cancelled";
}
