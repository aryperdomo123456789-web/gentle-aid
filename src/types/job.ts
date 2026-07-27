/** Tipos de domínio dos jobs de processamento (FFmpeg / esterilização). */

/** Status normalizado de um job de processamento. */
export type JobStatus = "queued" | "running" | "done" | "error" | "cancelled";

/** Ferramentas do ecossistema que geram jobs. */
export type ToolId = "youtube" | "tiktok" | "legendar" | "voice" | "canva";

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
  audit_summary?: string | null;
  sterilization?: SterilizationReport | null;
  outputs?: JobOutput[];
  artifacts?: { path: string; kind: string }[];
  source_kind?: "upload" | "download" | null;
  source_label?: string | null;
  source_path?: string | null;
  source_url?: string | null;
  log?: string[];
  meta?: Record<string, unknown>;
};

/** Um job terminou quando não há mais transições possíveis. */
export function isTerminalStatus(status: JobStatus): boolean {
  return status === "done" || status === "error" || status === "cancelled";
}
