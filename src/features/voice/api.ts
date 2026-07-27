import { apiGet, apiPostForm, apiPostJson } from "@/lib/http";
import type { Job } from "@/types/job";
import type {
  ScriptAnalysis,
  ScriptFixResult,
  ScriptStylesResponse,
  VoiceCatalog,
} from "./types";

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

/** Catálogo de estilos narrativos e ações do chat de roteiro. */
export function fetchScriptStyles(): Promise<ScriptStylesResponse> {
  return apiGet<ScriptStylesResponse>("/api/voice/script/styles");
}

/** Diagnóstico local do roteiro (não gasta IA). */
export function analyzeScript(text: string): Promise<{ analysis: ScriptAnalysis }> {
  return apiPostJson<{ analysis: ScriptAnalysis }>("/api/voice/script/analyze", { text });
}

/** Correção/reescrita do roteiro no estilo escolhido. */
export function fixScript(payload: {
  text: string;
  style: string;
  action: string;
  instruction?: string;
  seconds?: number;
}): Promise<ScriptFixResult> {
  return apiPostJson<ScriptFixResult>("/api/voice/script/fix", payload);
}
