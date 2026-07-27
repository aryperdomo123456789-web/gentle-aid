import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, FileDrop, SelectInput, SubmitButton, TextArea } from "@/components/form";
import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/components/StatusPanel";
import { ToolHistory } from "@/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiGet, apiPostForm, type Job } from "@/lib/api";

type RealisticVoice = { id: string; name: string; labels?: string; preview_url?: string };
type Catalog = {
  engine_ready: boolean;
  realistic_voices: RealisticVoice[];
  max_tts_chars: number;
};

type Mode = "media" | "text";

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
  const [engine, setEngine] = useState<Engine>("elevenlabs");
  const [ttsEngine, setTtsEngine] = useState<Engine>("elevenlabs");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const mediaForm = useRef<HTMLFormElement>(null);

  useEffect(() => {
    let alive = true;
    apiGet<Catalog>("/api/voice/catalog")
      .then((data) => {
        if (!alive) return;
        setCatalog(data);
        setPersonas(data.personas ?? []);
        if (!data.engine_ready) {
          const fallback: Engine = (data.personas ?? []).length > 0 ? "forge" : "local";
          setEngine(fallback);
          setTtsEngine("forge");
        }
      })
      .catch(() => setCatalog(null));
    return () => {
      alive = false;
    };
  }, []);

  const voices = catalog?.realistic_voices ?? [];
  const ready = catalog?.engine_ready ?? false;
  const forgeReady = (catalog?.forge_ready ?? false) && personas.length > 0;

  function processCard(card: DiscoveryCard) {
    const form = mediaForm.current ? new FormData(mediaForm.current) : new FormData();
    form.delete("media");
    form.set("url", card.url);
    form.set("source_card", JSON.stringify(card));
    setPickedUrl(card.url);
    run(() => apiPostForm<Job>("/api/voice/convert", form));
  }

  function submit(path: string) {
    return (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      run(() => apiPostForm<Job>(path, new FormData(e.currentTarget)));
    };
  }

  const voiceSelect = (id: string) => (
    <SelectInput id={id} name="voice_id" disabled={!ready}>
      {voices.map((v) => (
        <option key={v.id} value={v.id}>
          {v.name}
          {v.labels ? ` — ${v.labels}` : ""}
        </option>
      ))}
    </SelectInput>
  );

  const personaSelect = (id: string) => (
    <SelectInput id={id} name="persona_id" disabled={personas.length === 0}>
      {personas.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
      {personas.length === 0 ? <option value="">Crie uma voz na aba “Criar voz”</option> : null}
    </SelectInput>
  );


  return (
    <ToolShell
      badge="Ferramenta 4 · Estúdio de Voz"
      title="Troca de narrador e narração realista"
      subtitle="Vídeo ou áudio de 10 segundos a 3 horas: o narrador muda, a narrativa e o timing continuam idênticos. Ou escreva o roteiro e receba a narração pronta."
      left={
        <div className="space-y-5">
          <div className="flex gap-2 rounded-xl border border-border bg-background/40 p-1">
            {(
              [
                ["media", "Vídeo / Áudio → nova voz"],
                ["text", "Texto → narração"],
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

          {!ready ? (
            <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
              Chave ElevenLabs ausente. Cadastre o provedor <strong>ElevenLabs</strong> em <code>/apis</code> para
              liberar as vozes realistas e a narração por texto. Enquanto isso, o motor local de timbre segue
              disponível.
            </p>
          ) : null}

          {mode === "media" ? (
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

              <Field label="Motor de voz">
                {(id) => (
                  <SelectInput
                    id={id}
                    name="engine"
                    value={engine}
                    onChange={(e) => setEngine(e.target.value as "elevenlabs" | "local")}
                  >
                    <option value="elevenlabs" disabled={!ready}>
                      ElevenLabs — voz realista (speech-to-speech)
                    </option>
                    <option value="local">Local FFmpeg — troca de timbre (sem custo)</option>
                  </SelectInput>
                )}
              </Field>

              {engine === "elevenlabs" ? (
                <Field label="Voz do novo narrador" hint="A narrativa, a entonação e as pausas do original são preservadas.">
                  {voiceSelect}
                </Field>
              ) : (
                <Field label="Timbre alvo">
                  {(id) => (
                    <SelectInput id={id} name="target_voice" defaultValue="masc_grave">
                      <option value="masc_grave">Masculino grave</option>
                      <option value="masc_jovem">Masculino jovem</option>
                      <option value="fem_suave">Feminino suave</option>
                      <option value="fem_energetica">Feminino energética</option>
                      <option value="narrador">Narrador documentário</option>
                    </SelectInput>
                  )}
                </Field>
              )}

              <div className="grid gap-5 sm:grid-cols-2">
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

              <SubmitButton busy={busy} disabled={!hasFile}>
                {busy ? "Trocando o narrador…" : "Trocar a voz do narrador"}
              </SubmitButton>
            </form>
          ) : (
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

              <Field label="Voz da narração">{voiceSelect}</Field>

              <div className="grid gap-5 sm:grid-cols-2">
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

              <SubmitButton busy={busy} disabled={!ready}>
                {busy ? "Narrando…" : "Gerar narração"}
              </SubmitButton>
            </form>
          )}
        </div>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Envie um vídeo/áudio ou escreva um roteiro para começar."
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="auto"
            actionLabel="Trocar a voz deste vídeo"
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
