import type { Persona } from "@/components/VoiceForgePanel";
import type { LocalVoice, RealisticVoice } from "@/components/VoicePicker";

/** Catálogo de motores/vozes exposto por `/api/voice/catalog`. */
export type VoiceCatalog = {
  engine_ready: boolean;
  forge_ready: boolean;
  realistic_voices: RealisticVoice[];
  local_voices?: LocalVoice[];
  personas: Persona[];
  max_tts_chars: number;
  test_script?: string;
  dub_ready?: boolean;
  dub_languages?: Record<string, string>;
};

/** Abas do Estúdio de Voz. */
export type VoiceMode = "media" | "dub" | "text" | "forge";

/** Estilo narrativo do Doutor de Roteiro (`/api/voice/script/styles`). */
export type ScriptStyle = {
  id: string;
  label: string;
  emoji: string;
  resumo: string;
  ritmo: string;
  /** Velocidade sugerida para o TTS (string porque vai direto no <select>). */
  velocidade: string;
  /** Expressividade sugerida (0 a 1). */
  expressividade: number;
};

/** Ação rápida do chat de roteiro. */
export type ScriptAction = { id: string; label: string; hint: string };

/** Diagnóstico determinístico do roteiro. */
export type ScriptAnalysis = {
  words: number;
  sentences: number;
  chars: number;
  estimated_seconds: number;
  avg_words_per_sentence: number;
  hook: string;
  problems: string[];
};

export type ScriptStylesResponse = {
  styles: ScriptStyle[];
  actions: ScriptAction[];
  ai_ready: boolean;
  words_per_second: number;
};

export type ScriptFixResult = {
  script: string;
  changes: string[];
  note: string;
  provider: string | null;
  model: string | null;
  style: string;
  action: string;
  analysis: ScriptAnalysis;
  before?: ScriptAnalysis;
  fallback: boolean;
  elapsed?: number;
};
