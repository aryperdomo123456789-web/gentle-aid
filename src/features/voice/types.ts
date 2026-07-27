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
