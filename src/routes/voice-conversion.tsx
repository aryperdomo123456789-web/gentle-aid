import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, FileDrop, SelectInput, SubmitButton, TextArea, TextInput } from "@/components/form";
import { LinkInspector, type InspectedCard } from "@/components/LinkInspector";
import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/components/StatusPanel";
import { ToolHistory } from "@/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { VoiceForgePanel, type Persona } from "@/components/VoiceForgePanel";
import {
  VoicePicker,
  TEST_SCRIPT,
  type LocalVoice,
  type RealisticVoice,
  type VoiceSelection,
} from "@/components/VoicePicker";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiGet, apiPostForm, type Job } from "@/lib/api";

type Catalog = {
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

type Mode = "media" | "dub" | "text" | "forge";


export const Route = createFileRoute("/voice-conversion")({
  head: () => ({
    meta: [
      { title: "Estúdio de Voz — troca de narrador e narração realista" },
      {
        name: "description",
        content:
          "Troque a voz do narrador de vídeos e áudios de 10 segundos a 3 horas sem mudar a narrativa, ou transforme texto em narração realista.",
      },
      { property: "og:title", content: "Estúdio de Voz" },
      {
        property: "og:description",
        content: "Speech-to-speech e text-to-speech com vozes realistas, timing preservado e áudio esterilizado.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: VoiceStudio,
});

function VoiceStudio() {
  const { job, error, busy, run } = useJobRunner();
  const [mode, setMode] = useState<Mode>("media");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [hasFile, setHasFile] = useState(false);
  const [pickedUrl, setPickedUrl] = useState<string | null>(null);
  const [mediaVoice, setMediaVoice] = useState<VoiceSelection>({
    engine: "elevenlabs",
    voiceId: "",
    personaId: "",
    targetVoice: "masc_grave",
  });
  const [ttsVoice, setTtsVoice] = useState<VoiceSelection>({
    engine: "elevenlabs",
    voiceId: "",
    personaId: "",
    targetVoice: "masc_grave",
  });
  const [dubVoice, setDubVoice] = useState<VoiceSelection>({
    engine: "forge",
    voiceId: "",
    personaId: "",
    targetVoice: "masc_grave",
  });
  const [dubLink, setDubLink] = useState("");
  const [dubFile, setDubFile] = useState(false);
  const [mediaLink, setMediaLink] = useState("");
  const [mediaCard, setMediaCard] = useState<InspectedCard | null>(null);
  const [dubCard, setDubCard] = useState<InspectedCard | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const mediaForm = useRef<HTMLFormElement>(null);
  const dubForm = useRef<HTMLFormElement>(null);


  useEffect(() => {
    let alive = true;
    apiGet<Catalog>("/api/voice/catalog")
      .then((data) => {
        if (!alive) return;
        setCatalog(data);
        setPersonas(data.personas ?? []);
        const firstVoice = data.realistic_voices?.[0]?.id ?? "";
        const firstPersona = data.personas?.[0]?.id ?? "";
        const hasPersona = (data.personas ?? []).length > 0;
        setMediaVoice((prev) => ({
          ...prev,
          engine: data.engine_ready ? "elevenlabs" : hasPersona ? "forge" : "local",
          voiceId: prev.voiceId || firstVoice,
          personaId: prev.personaId || firstPersona,
        }));
        setTtsVoice((prev) => ({
          ...prev,
          engine: data.engine_ready ? "elevenlabs" : "forge",
          voiceId: prev.voiceId || firstVoice,
          personaId: prev.personaId || firstPersona,
        }));
        setDubVoice((prev) => ({
          ...prev,
          engine: hasPersona ? "forge" : data.engine_ready ? "elevenlabs" : "forge",
          voiceId: prev.voiceId || firstVoice,
          personaId: prev.personaId || firstPersona,
        }));
      })
      .catch(() => setCatalog(null));
    return () => {
      alive = false;
    };
  }, []);

  const voices = catalog?.realistic_voices ?? [];
  const ready = catalog?.engine_ready ?? false;
  const forgeReady = (catalog?.forge_ready ?? false) && personas.length > 0;
  const testScript = catalog?.test_script || TEST_SCRIPT;

  function processCard(card: DiscoveryCard) {
    const isDub = mode === "dub";
    const ref = isDub ? dubForm.current : mediaForm.current;
    const form = ref ? new FormData(ref) : new FormData();
    form.delete("media");
    form.set("url", card.url);
    form.set("source_card", JSON.stringify(card));
    setPickedUrl(card.url);
    run(() => apiPostForm<Job>(isDub ? "/api/voice/dub" : "/api/voice/convert", form));
  }

  function submit(path: string) {
    return (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const form = new FormData(e.currentTarget);
      const card = path.endsWith("/dub") ? dubCard : mediaCard;
      const url = String(form.get("url") || "").trim();
      if (card && card.url === url) form.set("source_card", JSON.stringify(card));
      run(() => apiPostForm<Job>(path, form));
    };
  }


  const mediaPicker = (
    <VoicePicker
      value={mediaVoice}
      onChange={setMediaVoice}
      realisticVoices={voices}
      personas={personas}
      localVoices={catalog?.local_voices}
      elevenReady={ready}
      forgeReady={forgeReady}
      allowLocal
      testScript={testScript}
    />
  );

  const dubPicker = (
    <VoicePicker
      value={dubVoice}
      onChange={setDubVoice}
      realisticVoices={voices}
      personas={personas}
      elevenReady={ready}
      forgeReady={forgeReady}
      allowLocal={false}
      testScript={testScript}
    />
  );

  const ttsPicker = (
    <VoicePicker
      value={ttsVoice}
      onChange={setTtsVoice}
      realisticVoices={voices}
      personas={personas}
      elevenReady={ready}
      forgeReady={forgeReady}
      allowLocal={false}
      testScript={testScript}
    />
  );



  return (
    <ToolShell
      badge="Ferramenta 4 · Estúdio de Voz"
      title="Troca de narrador e narração realista"
      subtitle="Link do YouTube/TikTok, upload ou roteiro: a IA escuta a narração original e dubla com a sua voz, no mesmo timing, de 10 segundos a 3 horas."
      left={
        <div className="space-y-5">
          <div className="flex gap-2 rounded-xl border border-border bg-background/40 p-1">
            {(
              [
                ["media", "Trocar timbre"],
                ["dub", "Dublagem IA"],
                ["text", "Texto → narração"],
                ["forge", "Criar voz"],
              ] as const
            ).map(([value, label]) => (

              <button
                key={value}
                type="button"
                onClick={() => setMode(value)}
                className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
                  mode === value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {!ready && mode !== "forge" ? (
            <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
              Chave ElevenLabs ausente. Cadastre o provedor <strong>ElevenLabs</strong> em <code>/apis</code> para
              liberar as vozes realistas. Enquanto isso, use a aba <strong>Criar voz</strong> — o Voice Forge gera
              uma voz exclusiva sua sem nenhum custo.
            </p>
          ) : null}

          {mode === "forge" ? (
            <VoiceForgePanel onChanged={setPersonas} />
          ) : mode === "media" ? (
            <form ref={mediaForm} onSubmit={submit("/api/voice/convert")} className="space-y-5">
              <Field label="Vídeo ou áudio de origem" hint="MP4, MOV, MKV, WAV, MP3 ou M4A — arquivos longos são fatiados automaticamente.">
                {(id) => (
                  <FileDrop
                    id={id}
                    name="media"
                    accept="video/mp4,video/quicktime,video/x-matroska,video/webm,audio/wav,audio/mpeg,audio/mp4,audio/x-m4a"
                    hint="MP4 / MOV / MKV / WAV / MP3 / M4A"
                    onSelect={(f) => setHasFile(Boolean(f))}
                  />
                )}
              </Field>

              <Field
                label="Ou cole o link do YouTube / TikTok"
                hint="O vídeo é baixado no servidor e processado direto — sem precisar do arquivo."
              >
                {(id) => (
                  <TextInput
                    id={id}
                    name="url"
                    inputMode="url"
                    placeholder="https://www.youtube.com/watch?v=… ou https://www.tiktok.com/@perfil/video/…"
                    value={mediaLink}
                    onChange={(e) => setMediaLink(e.target.value)}
                  />
                )}
              </Field>

              {mediaPicker}


              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
                <Field label="Saída quando for vídeo">
                  {(id) => (
                    <SelectInput id={id} name="keep_video" defaultValue="1">
                      <option value="1">Vídeo com a nova narração</option>
                      <option value="0">Somente o áudio convertido</option>
                    </SelectInput>
                  )}
                </Field>
                <Field label="Formato do áudio">
                  {(id) => (
                    <SelectInput id={id} name="format" defaultValue="mp3">
                      <option value="mp3">MP3 320 kbps</option>
                      <option value="wav">WAV 48 kHz</option>
                      <option value="aac">AAC 192 kbps</option>
                    </SelectInput>
                  )}
                </Field>
              </div>

              <Field label="Preservar timing">
                {(id) => (
                  <SelectInput id={id} name="preserve_timing" defaultValue="strict">
                    <option value="strict">Estrito — mesma duração exata (sincroniza com o vídeo)</option>
                    <option value="natural">Natural — deixa a prosódia respirar</option>
                  </SelectInput>
                )}
              </Field>

              <MutationSelect
                defaultValue="auto"
                label="Esterilização"
                hint="Remove metadados/ID3 herdados e entrega um arquivo de hash inédito."
              />

              <SubmitButton busy={busy} disabled={!hasFile && mediaLink.trim().length < 8}>
                {busy ? "Trocando o narrador…" : "Trocar a voz do narrador"}
              </SubmitButton>
            </form>
          ) : mode === "dub" ? (
            <form ref={dubForm} onSubmit={submit("/api/voice/dub")} className="space-y-5">
              {catalog && catalog.dub_ready === false ? (
                <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                  A dublagem precisa <strong>ouvir</strong> o vídeo. Cadastre a chave <strong>Groq</strong> (ou
                  Whisper) em <code>/apis</code> para liberar a transcrição com timestamps.
                </p>
              ) : null}

              <Field
                label="Link do YouTube ou TikTok"
                hint="O servidor baixa o vídeo, escuta a narração e refaz o áudio com a sua voz — sincronizado no mesmo timing."
              >
                {(id) => (
                  <TextInput
                    id={id}
                    name="url"
                    inputMode="url"
                    placeholder="https://www.youtube.com/watch?v=… ou https://www.tiktok.com/@perfil/video/…"
                    value={dubLink}
                    onChange={(e) => setDubLink(e.target.value)}
                  />
                )}
              </Field>

              <LinkInspector
                url={dubLink}
                onInspected={setDubCard}
                actionLabel="Dublar este vídeo"
                actionBusy={busy}
                onAction={processCard}
              />



              <Field label="Ou envie o arquivo" hint="MP4 / MOV / MKV / WAV / MP3 / M4A — de 10 segundos a 3 horas.">
                {(id) => (
                  <FileDrop
                    id={id}
                    name="media"
                    accept="video/mp4,video/quicktime,video/x-matroska,video/webm,audio/wav,audio/mpeg,audio/mp4,audio/x-m4a"
                    hint="MP4 / MOV / MKV / WAV / MP3 / M4A"
                    onSelect={(f) => setDubFile(Boolean(f))}
                  />
                )}
              </Field>

              {dubPicker}

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
                <Field label="Idioma da dublagem">
                  {(id) => (
                    <SelectInput id={id} name="target_lang" defaultValue="auto">
                      {Object.entries(catalog?.dub_languages ?? { auto: "mesmo idioma do vídeo" }).map(
                        ([code, label]) => (
                          <option key={code} value={code}>
                            {label}
                          </option>
                        ),
                      )}
                    </SelectInput>
                  )}
                </Field>
                <Field label="Áudio original ao fundo">
                  {(id) => (
                    <SelectInput id={id} name="keep_ambience" defaultValue="0.12">
                      <option value="0">Remover — só a nova narração</option>
                      <option value="0.12">Leve — música e ambiência discretas</option>
                      <option value="0.3">Médio — mantém a trilha audível</option>
                    </SelectInput>
                  )}
                </Field>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
                <Field label="Saída">
                  {(id) => (
                    <SelectInput id={id} name="keep_video" defaultValue="1">
                      <option value="1">Vídeo dublado</option>
                      <option value="0">Somente o áudio dublado</option>
                    </SelectInput>
                  )}
                </Field>
                <Field label="Formato do áudio">
                  {(id) => (
                    <SelectInput id={id} name="format" defaultValue="mp3">
                      <option value="mp3">MP3 320 kbps</option>
                      <option value="wav">WAV 48 kHz</option>
                      <option value="aac">AAC 192 kbps</option>
                    </SelectInput>
                  )}
                </Field>
              </div>

              <MutationSelect
                defaultValue="auto"
                label="Esterilização"
                hint="O vídeo dublado sai virgem: sem metadados herdados e com hash inédito."
              />

              <SubmitButton busy={busy} disabled={!dubFile && dubLink.trim().length < 8}>
                {busy ? "Dublando com IA…" : "Dublar com a minha voz"}
              </SubmitButton>
            </form>
          ) : mode === "text" ? (
            <form onSubmit={submit("/api/voice/tts")} className="space-y-5">
              <Field
                label="Roteiro"
                hint={`Até ${(catalog?.max_tts_chars ?? 40000).toLocaleString("pt-BR")} caracteres — textos longos viram uma narração contínua.`}
              >
                {(id) => (
                  <TextArea
                    id={id}
                    name="text"
                    placeholder="Cole aqui o roteiro que será narrado…"
                    maxLength={catalog?.max_tts_chars ?? 40000}
                  />
                )}
              </Field>

              {ttsPicker}



              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
                <Field label="Velocidade">
                  {(id) => (
                    <SelectInput id={id} name="speed" defaultValue="1">
                      <option value="0.9">Pausada (0.9x)</option>
                      <option value="1">Natural (1.0x)</option>
                      <option value="1.1">Ágil (1.1x)</option>
                    </SelectInput>
                  )}
                </Field>
                <Field label="Formato">
                  {(id) => (
                    <SelectInput id={id} name="format" defaultValue="mp3">
                      <option value="mp3">MP3 320 kbps</option>
                      <option value="wav">WAV 48 kHz</option>
                      <option value="aac">AAC 192 kbps</option>
                    </SelectInput>
                  )}
                </Field>
              </div>

              <Field label="Expressividade">
                {(id) => (
                  <SelectInput id={id} name="style" defaultValue="0.15">
                    <option value="0">Neutra — leitura limpa</option>
                    <option value="0.15">Narrador — padrão do mercado</option>
                    <option value="0.45">Dramática — storytelling viral</option>
                  </SelectInput>
                )}
              </Field>

              <MutationSelect defaultValue="auto" label="Esterilização" hint="Áudio final sem rastro de origem." />

              <SubmitButton busy={busy} disabled={ttsVoice.engine === "elevenlabs" ? !ready : !forgeReady}>
                {busy ? "Narrando…" : "Gerar narração"}
              </SubmitButton>
            </form>
          ) : null}
        </div>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Cole o link do YouTube/TikTok, envie um arquivo ou escreva um roteiro para começar."
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="auto"
            actionLabel={mode === "dub" ? "Dublar este vídeo" : "Trocar a voz deste vídeo"}
            onAction={processCard}
            actionBusyUrl={busy ? pickedUrl : null}
          />
          <ToolHistory
            tool="voice"
            title="Histórico · Estúdio de Voz"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
