import { apiDelete, apiGet, apiPostForm, apiPostJson } from "@/lib/http";
import type { Job } from "@/types/job";

/** Endpoints do Recap Narrado (`/api/recap`). */

export type RecapFormat = {
  id: "short" | "long";
  label: string;
  hint: string;
  width: number;
  height: number;
  min_seconds: number;
  max_seconds: number;
  default_seconds: number;
  frame_mode: "crop" | "pad";
};

export type RecapStyle = {
  id: string;
  label: string;
  emoji: string;
  resumo: string;
  ritmo: string;
  velocidade: string;
  expressividade: number;
};

export type RecapPersona = { id: string; name: string; notes?: string };

export type CaptionPreset = {
  id: string;
  label: string;
  tag: string;
  description: string;
};

/** Preset de blocos fixos (abertura, meio e fecho) salvo no servidor. */
export type BlockPreset = {
  id: string;
  name: string;
  abertura: string;
  meio: string;
  fecho: string;
};

export type RecapCatalog = {
  formats: RecapFormat[];
  styles: RecapStyle[];
  personas: RecapPersona[];
  caption_presets: CaptionPreset[];
  blocks: BlockPreset[];
  words_per_second: number;
  ai_ready: boolean;
  vision_ready: boolean;
  forge_ready: boolean;
  elevenlabs_ready: boolean;
};

export function fetchRecapCatalog(): Promise<RecapCatalog> {
  return apiGet<RecapCatalog>("/api/recap/catalog");
}

export function saveBlockPreset(payload: {
  id?: string;
  name: string;
  abertura: string;
  meio: string;
  fecho: string;
}): Promise<{ preset: BlockPreset; blocks: BlockPreset[] }> {
  return apiPostJson("/api/recap/blocks", payload);
}

export function deleteBlockPreset(presetId: string): Promise<{ blocks: BlockPreset[] }> {
  return apiDelete(`/api/recap/blocks/${presetId}`);
}

export function submitRecapJob(form: FormData): Promise<Job> {
  return apiPostForm<Job>("/api/recap/run", form);
}
