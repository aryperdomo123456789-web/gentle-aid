import { apiGet, apiPostJson } from "@/lib/http";

/** Endpoints da Fábrica de Cortes (`/api/clips`). */

export type ClipNiche = {
  id: string;
  label: string;
  emoji?: string;
  resumo?: string;
};

export type ClipPreset = {
  id: string;
  label: string;
  vibe?: string;
};

export type ClipOptions = {
  niches: ClipNiche[];
  aspects: string[];
  frames: string[];
  presets: ClipPreset[];
  positions: string[];
  transcription: boolean;
  transcription_hint?: string | null;
  ai_ready: boolean;
  max_clips: number;
};

export type ClipResult = {
  index: number;
  title: string;
  start: number;
  end: number;
  seconds: number;
  score?: number | null;
  ai_score?: number | null;
  reasons?: string[];
  filename: string;
  download_url: string;
  md5_after?: string;
  size_bytes?: number;
};

export function fetchClipOptions(): Promise<ClipOptions> {
  return apiGet<ClipOptions>("/api/clips/options");
}

/** Simula a curadoria a partir de um SRT, sem gastar processamento. */
export function previewClips(payload: {
  srt: string;
  niche: string;
  min_seconds: number;
  max_seconds: number;
}): Promise<{ clips: ClipResult[]; total: number }> {
  return apiPostJson("/api/clips/preview", payload);
}
