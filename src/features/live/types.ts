/** Tipos da Estação de Live 24/7 (RTMP em loop). */

export type LivePlatform = "youtube" | "tiktok";

export type LiveStatus =
  | "idle"
  | "starting"
  | "live"
  | "reconnecting"
  | "stopping"
  | "stopped"
  | "error";

export type LivePreset = {
  id: string;
  label: string;
  width: number;
  height: number;
  fps: number;
  bitrate: number;
};

export type LivePlatformInfo = {
  id: LivePlatform;
  label: string;
  note: string;
  default_url: string;
  default_preset: string;
  key_configured: boolean;
  provider_id: string;
};

export type LiveOptions = {
  platforms: LivePlatformInfo[];
  presets: LivePreset[];
};

export type LibraryItem = {
  tool: string;
  name: string;
  path: string;
  size_bytes: number;
  modified_at: number;
};

export type LiveMetrics = {
  frames?: number;
  fps?: number;
  time?: string;
  bitrate?: string;
  dropped?: number;
  speed?: number;
};

export type LiveSession = {
  session_id?: string;
  platform: LivePlatform;
  platform_label?: string;
  status: LiveStatus;
  preset?: string;
  preset_label?: string;
  sources?: string[];
  overlay?: { clock?: boolean; counter?: boolean; text?: string };
  rtmp_host?: string;
  attempts?: number;
  reconnects?: number;
  max_retries?: number;
  created_at?: string;
  started_at?: string;
  updated_at?: string;
  stopped_at?: string | null;
  uptime_seconds?: number;
  error?: string | null;
  metrics?: LiveMetrics;
  log?: string[];
};

export const ACTIVE_STATUSES: LiveStatus[] = ["starting", "live", "reconnecting", "stopping"];

export function isLiveActive(status?: LiveStatus): boolean {
  return Boolean(status && ACTIVE_STATUSES.includes(status));
}
