import { useEffect, useRef, useState } from "react";

import type { DiscoveryCard } from "@/components/DiscoveryPanel";
import type { InspectedCard } from "@/components/LinkInspector";
import type { Persona } from "@/components/VoiceForgePanel";
import { TEST_SCRIPT, type VoiceSelection } from "@/components/VoicePicker";
import { useJobRunner } from "@/hooks/use-job-runner";
import { fetchVoiceCatalog, resetVoicePersonas, submitVoiceJob, VOICE_ENDPOINT } from "./api";
import type { VoiceCatalog, VoiceMode } from "./types";

const DEFAULT_SELECTION: VoiceSelection = {
  engine: "elevenlabs",
  voiceId: "",
  personaId: "",
  targetVoice: "masc_grave",
};

/** Estado do Estúdio de Voz: catálogo, seleção por aba e submissão dos jobs. */
export function useVoiceStudio() {
  const runner = useJobRunner("voice");
  const { busy, run } = runner;

  const [mode, setMode] = useState<VoiceMode>("forge");
  const [catalog, setCatalog] = useState<VoiceCatalog | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);

  const [hasFile, setHasFile] = useState(false);
  const [dubFile, setDubFile] = useState(false);
  const [pickedUrl, setPickedUrl] = useState<string | null>(null);

  const [mediaVoice, setMediaVoice] = useState<VoiceSelection>(DEFAULT_SELECTION);
  const [ttsVoice, setTtsVoice] = useState<VoiceSelection>(DEFAULT_SELECTION);
  const [dubVoice, setDubVoice] = useState<VoiceSelection>({
    ...DEFAULT_SELECTION,
    engine: "forge",
  });

  const [mediaLink, setMediaLink] = useState("");
  const [dubLink, setDubLink] = useState("");
  const [mediaCard, setMediaCard] = useState<InspectedCard | null>(null);
  const [dubCard, setDubCard] = useState<InspectedCard | null>(null);

  const mediaForm = useRef<HTMLFormElement>(null);
  const dubForm = useRef<HTMLFormElement>(null);

  useEffect(() => {
    let alive = true;
    fetchVoiceCatalog()
      .then((data) => {
        if (!alive) return;
        setCatalog(data);
        setPersonas(data.personas ?? []);
        const firstVoice = data.realistic_voices?.[0]?.id ?? "";
        const firstPersona = data.personas?.[0]?.id ?? "";
        const hasPersona = (data.personas ?? []).length > 0;
        const withDefaults = (engine: VoiceSelection["engine"]) => (prev: VoiceSelection) => ({
          ...prev,
          engine,
          voiceId: prev.voiceId || firstVoice,
          personaId: prev.personaId || firstPersona,
        });
        setMediaVoice(
          withDefaults(data.engine_ready ? "elevenlabs" : hasPersona ? "forge" : "local"),
        );
        setTtsVoice(withDefaults(data.engine_ready ? "elevenlabs" : "forge"));
        setDubVoice(
          withDefaults(hasPersona ? "forge" : data.engine_ready ? "elevenlabs" : "forge"),
        );
      })
      .catch(() => setCatalog(null));
    return () => {
      alive = false;
    };
  }, []);

  /** Dispara o job a partir de um card de descoberta, reusando o formulário aberto. */
  function processCard(card: DiscoveryCard) {
    const isDub = mode === "dub";
    const ref = isDub ? dubForm.current : mediaForm.current;
    const form = ref ? new FormData(ref) : new FormData();
    form.delete("media");
    form.set("url", card.url);
    form.set("source_card", JSON.stringify(card));
    setPickedUrl(card.url);
    run(() => submitVoiceJob(isDub ? VOICE_ENDPOINT.dub : VOICE_ENDPOINT.convert, form));
  }

  /** Handler de submit que anexa o card inspecionado quando o link bate. */
  function submit(path: string) {
    return (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const form = new FormData(e.currentTarget);
      const card = path === VOICE_ENDPOINT.dub ? dubCard : mediaCard;
      const url = String(form.get("url") || "").trim();
      if (card && card.url === url) form.set("source_card", JSON.stringify(card));
      run(() => submitVoiceJob(path, form));
    };
  }

  const voices = catalog?.realistic_voices ?? [];
  const elevenReady = catalog?.engine_ready ?? false;
  const forgeReady = (catalog?.forge_ready ?? false) && personas.length > 0;

  async function syncPersonas() {
    const data = await resetVoicePersonas();
    setCatalog(data);
    setPersonas(data.personas ?? []);
  }

  return {
    ...runner,
    busy,
    mode,
    setMode,
    catalog,
    personas,
    setPersonas,
    voices,
    elevenReady,
    forgeReady,
    syncPersonas,
    testScript: catalog?.test_script || TEST_SCRIPT,
    maxChars: catalog?.max_tts_chars ?? 40000,
    dubReady: catalog ? catalog.dub_ready !== false : true,
    dubTranslateReady: catalog ? catalog.dub_translate_ready !== false : true,
    dubLanguages: catalog?.dub_languages ?? { auto: "mesmo idioma do vídeo" },

    hasFile,
    setHasFile,
    dubFile,
    setDubFile,
    pickedUrl,
    mediaVoice,
    setMediaVoice,
    ttsVoice,
    setTtsVoice,
    dubVoice,
    setDubVoice,
    mediaLink,
    setMediaLink,
    dubLink,
    setDubLink,
    setMediaCard,
    setDubCard,
    mediaForm,
    dubForm,
    processCard,
    submit,
  };
}
