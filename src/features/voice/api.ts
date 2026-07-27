import { apiGet, apiPostForm, apiPostJson } from "@/lib/http";
import type { Job } from "@/types/job";
import type { VoiceCatalog } from "./types";

/** Endpoints do Estúdio de Voz (`/api/voice`). */

export const VOICE_ENDPOINT = {
  convert: "/api/voice/convert",
  dub: "/api/voice/dub",
  tts: "/api/voice/tts",
} as const;

export function fetchVoiceCatalog(): Promise<VoiceCatalog> {
  return apiGet<VoiceCatalog>("/api/voice/catalog");
}

export function resetVoicePersonas(): Promise<VoiceCatalog> {
  return apiPostJson<VoiceCatalog>("/api/voice/personas/reset", {});
}

export function submitVoiceJob(path: string, form: FormData): Promise<Job> {
  return apiPostForm<Job>(path, form);
}
