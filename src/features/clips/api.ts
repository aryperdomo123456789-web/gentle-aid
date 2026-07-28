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
  soundtrack?: ClipSoundtrackCatalog;
};

export type ClipTrack = {
  id: string;
  label: string;
  origin: string;
  grid_bpm?: number;
  bpm: number;
  duration: number;
  tags?: string[];
  profile?: string | null;
  reason?: string;
};

export type ClipMusicProfile = {
  id: string;
  label: string;
  bpm: number;
  energy: number;
  tags?: string[];
};

export type ClipSoundtrackCatalog = {
  modes: string[];
  profiles: ClipMusicProfile[];
  tracks: ClipTrack[];
  library_dir?: string;
  ai_ready?: boolean;
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

export function fetchClipTracks(): Promise<{ tracks: ClipTrack[]; library_dir: string }> {
  return apiGet("/api/clips/tracks");
}

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
