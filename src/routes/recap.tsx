import { createFileRoute } from "@tanstack/react-router";
import { Bookmark, Eye, Loader2, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, FileDrop, SelectInput, TextArea, TextInput } from "@/components/form";
import { JobSettingsGuard } from "@/components/JobSettingsGuard";
import { MutationSelect } from "@/components/MutationSelect";
import { ToolShell } from "@/components/ToolShell";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import {
  deleteBlockPreset,
  fetchRecapCatalog,
  saveBlockPreset,
  submitRecapJob,
  type BlockPreset,
  type RecapCatalog,
} from "@/features/recap/api";
import { useJobRunner } from "@/hooks/use-job-runner";
import { friendlyError } from "@/lib/api";

export const Route = createFileRoute("/recap")({
  head: () => ({
    meta: [
      { title: "Recap Narrado — resumo de filme e série com IA" },
      {
        name: "description",
        content:
          "Transcreve, lê as cenas, entende o arco da história e reconta o vídeo com a sua voz em 9:16 ou 16:9, com legenda animada e hash inédito.",
      },
      { property: "og:title", content: "Recap Narrado — resumo narrado por IA" },
      {
        property: "og:description",
        content:
          "Motor que ouve o áudio, assiste às cenas e escreve a narração ancorada nos melhores momentos do vídeo.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: RecapPage,
});

function mmss(total: number): string {
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}min${seconds ? ` ${seconds}s` : ""}`;
}

function RecapPage() {
  const { job, error, busy, run, cancel, remove } = useJobRunner("recap");
  const formRef = useRef<HTMLFormElement>(null);

  const [catalog, setCatalog] = useState<RecapCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [hasFile, setHasFile] = useState(false);
  const [card, setCard] = useState<DiscoveryCard | null>(null);

  const [format, setFormat] = useState<"short" | "long">("short");
  const [seconds, setSeconds] = useState(120);
  const [engine, setEngine] = useState<"forge" | "elevenlabs">("forge");
  const [withCaptions, setWithCaptions] = useState(true);
  const [vision, setVision] = useState(true);

  const [abertura, setAbertura] = useState("");
  const [meio, setMeio] = useState("");
  const [fecho, setFecho] = useState("");
  const [presetName, setPresetName] = useState("");
  const [presets, setPresets] = useState<BlockPreset[]>([]);
  const [savingPreset, setSavingPreset] = useState(false);
  const [presetError, setPresetError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchRecapCatalog()
      .then((data) => {
        if (!alive) return;
        setCatalog(data);
        setPresets(data.blocks);
        setVision(data.vision_ready);
        if (!data.forge_ready && data.elevenlabs_ready) setEngine("elevenlabs");
      })
      .catch((err) => alive && setCatalogError(friendlyError(err)));
    return () => {
      alive = false;
    };
  }, []);

  const activeFormat = useMemo(
    () => catalog?.formats.find((f) => f.id === format) ?? null,
    [catalog, format],
  );

  // Trocar de formato reposiciona a duração dentro da faixa permitida.
  useEffect(() => {
    if (!activeFormat) return;
    setSeconds((current) =>
      current < activeFormat.min_seconds || current > activeFormat.max_seconds
        ? activeFormat.default_seconds
        : current,
    );
  }, [activeFormat]);

  const words = catalog ? Math.round(seconds * catalog.words_per_second) : 0;

  function applyPreset(preset: BlockPreset) {
    setAbertura(preset.abertura);
    setMeio(preset.meio);
    setFecho(preset.fecho);
    setPresetName(preset.name);
  }

  async function handleSavePreset() {
    if (!presetName.trim()) {
      setPresetError("Dê um nome ao preset antes de salvar.");
      return;
    }
    setSavingPreset(true);
    setPresetError(null);
    try {
      const data = await saveBlockPreset({ name: presetName, abertura, meio, fecho });
      setPresets(data.blocks);
    } catch (err) {
      setPresetError(friendlyError(err));
    } finally {
      setSavingPreset(false);
    }
  }

  async function handleDeletePreset(presetId: string) {
    try {
      const data = await deleteBlockPreset(presetId);
      setPresets(data.blocks);
    } catch (err) {
      setPresetError(friendlyError(err));
    }
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    form.set("captions", withCaptions ? "1" : "0");
    form.set("vision", vision ? "1" : "0");
    run(() => submitRecapJob(form));
  }

  const blocked = !catalog?.ai_ready;

  return (
    <ToolShell
      badge="Ferramenta 7 · /api/recap/run"
      title="Recap Narrado"
      subtitle="O motor ouve o áudio, assiste às cenas com IA multimodal, entende o arco da história e reconta tudo com a sua voz — trechos curtos, narração nova por cima e legenda animada."
      left={
        <form ref={formRef} onSubmit={onSubmit} className="space-y-5">
          {catalogError ? (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              {catalogError}
            </p>
          ) : null}
          {catalog && !catalog.ai_ready ? (
            <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200">
              Cadastre em <span className="font-semibold">/apis</span> a chave de um LLM (DeepSeek,
              Groq, OpenRouter ou Mistral) — é ela que entende a história e escreve a narração.
            </p>
          ) : null}

          {card ? (
            <div className="rounded-xl border border-primary/40 bg-primary/5 p-3 text-xs">
              <p className="font-medium text-foreground">Vídeo da pesquisa selecionado</p>
              <p className="mt-1 truncate text-muted-foreground">{card.title}</p>
              <input type="hidden" name="url" value={card.url} />
              <input type="hidden" name="source_card" value={JSON.stringify(card)} />
              <button
                type="button"
                onClick={() => setCard(null)}
                className="mt-2 rounded-lg border border-border px-3 py-1 text-[11px] text-muted-foreground transition hover:text-foreground"
              >
                Remover seleção
              </button>
            </div>
          ) : null}

          <Field label="Vídeo longo" hint="MP4, MOV, MKV ou WEBM. Use conteúdo próprio ou faça recap comentado.">
            {(id) => (
              <FileDrop
                id={id}
                name="video"
                accept="video/mp4,video/quicktime,video/x-matroska,video/webm"
                hint="MP4 / MOV / MKV / WEBM"
                onSelect={(f) => setHasFile(Boolean(f))}
              />
            )}
          </Field>

          {!card ? (
            <Field label="Ou cole um link público" hint="YouTube, TikTok ou qualquer link aberto.">
              {(id) => <TextInput id={id} name="url" placeholder="https://…" inputMode="url" />}
            </Field>
          ) : null}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Formato de saída" hint={activeFormat?.hint}>
              {(id) => (
                <SelectInput
                  id={id}
                  name="format"
                  value={format}
                  onChange={(e) => setFormat(e.target.value as "short" | "long")}
                >
                  {(catalog?.formats ?? []).map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>

            <Field
              label={`Duração alvo · ${mmss(seconds)}`}
              hint={words ? `≈ ${words} palavras de narração` : undefined}
            >
              {(id) => (
                <input
                  id={id}
                  name="target_seconds"
                  type="range"
                  min={activeFormat?.min_seconds ?? 45}
                  max={activeFormat?.max_seconds ?? 240}
                  step={15}
                  value={seconds}
                  onChange={(e) => setSeconds(Number(e.target.value))}
                  className="h-11 w-full accent-primary"
                />
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Estilo da narração" hint="Define o tom que a IA usa para reescrever.">
              {(id) => (
                <SelectInput id={id} name="style" defaultValue="documentario">
                  {(catalog?.styles ?? []).map((style) => (
                    <option key={style.id} value={style.id}>
                      {style.emoji} {style.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>

            <Field label="Motor de voz">
              {(id) => (
                <SelectInput
                  id={id}
                  name="engine"
                  value={engine}
                  onChange={(e) => setEngine(e.target.value as "forge" | "elevenlabs")}
                >
                  <option value="forge">Voz própria (Voice Forge)</option>
                  <option value="elevenlabs" disabled={!catalog?.elevenlabs_ready}>
                    Voz realista (ElevenLabs)
                  </option>
                </SelectInput>
              )}
            </Field>
          </div>

          {engine === "forge" ? (
            <Field label="Voz própria (persona)" hint="A mesma persona do Estúdio de Voz.">
              {(id) => (
                <SelectInput id={id} name="persona_id" defaultValue={catalog?.personas[0]?.id}>
                  {(catalog?.personas ?? []).map((persona) => (
                    <option key={persona.id} value={persona.id}>
                      {persona.name}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
          ) : (
            <Field label="ID da voz realista" hint="Cole o voice_id do ElevenLabs.">
              {(id) => <TextInput id={id} name="voice_id" placeholder="21m00Tcm4TlvDq8ikWAM" />}
            </Field>
          )}

          <fieldset className="space-y-3 rounded-xl border border-border bg-background/40 p-3">
            <legend className="px-1 text-xs font-semibold text-muted-foreground">
              Blocos fixos do canal
            </legend>

            {presets.length ? (
              <div className="flex flex-wrap gap-2">
                {presets.map((preset) => (
                  <span
                    key={preset.id}
                    className="inline-flex items-center gap-1 rounded-full border border-border bg-surface/60 pl-3 pr-1 text-xs"
                  >
                    <button
                      type="button"
                      onClick={() => applyPreset(preset)}
                      className="py-1.5 font-medium text-foreground transition hover:text-primary"
                    >
                      {preset.name}
                    </button>
                    <button
                      type="button"
                      aria-label={`Apagar preset ${preset.name}`}
                      onClick={() => handleDeletePreset(preset.id)}
                      className="rounded-full p-1.5 text-muted-foreground transition hover:text-destructive"
                    >
                      <Trash2 className="size-3.5" aria-hidden="true" />
                    </button>
                  </span>
                ))}
              </div>
            ) : null}

            <Field label="Abertura" hint="Vai antes de tudo, no primeiro trecho.">
              {(id) => (
                <TextArea
                  id={id}
                  name="abertura"
                  rows={2}
                  value={abertura}
                  onChange={(e) => setAbertura(e.target.value)}
                  placeholder="Esse filme escondeu o final desde a primeira cena…"
                  className="min-h-20"
                />
              )}
            </Field>
            <Field label="Meio" hint="O clássico 'segue o canal, parte 2 amanhã'.">
              {(id) => (
                <TextArea
                  id={id}
                  name="meio"
                  rows={2}
                  value={meio}
                  onChange={(e) => setMeio(e.target.value)}
                  placeholder="Segue o canal que a parte dois sai amanhã."
                  className="min-h-20"
                />
              )}
            </Field>
            <Field label="Fecho" hint="Última fala do vídeo.">
              {(id) => (
                <TextArea
                  id={id}
                  name="fecho"
                  rows={2}
                  value={fecho}
                  onChange={(e) => setFecho(e.target.value)}
                  placeholder="Comenta aí o que você faria no lugar dela."
                  className="min-h-20"
                />
              )}
            </Field>

            <div className="flex flex-col gap-2 sm:flex-row">
              <TextInput
                value={presetName}
                onChange={(e) => setPresetName(e.target.value)}
                placeholder="Nome do preset (ex.: Canal de terror)"
                aria-label="Nome do preset de blocos"
              />
              <button
                type="button"
                onClick={handleSavePreset}
                disabled={savingPreset}
                className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-border bg-secondary px-4 text-sm font-semibold text-secondary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {savingPreset ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Bookmark className="size-4" aria-hidden="true" />
                )}
                Salvar preset
              </button>
            </div>
            {presetError ? <p className="text-xs text-destructive">{presetError}</p> : null}
          </fieldset>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Áudio original ao fundo" hint="0 = só a narração. 0.12 mantém a ambiência.">
              {(id) => (
                <SelectInput id={id} name="ambience" defaultValue="0.12">
                  <option value="0">Silenciar o original</option>
                  <option value="0.08">Bem baixo (0.08)</option>
                  <option value="0.12">Padrão (0.12)</option>
                  <option value="0.25">Presente (0.25)</option>
                </SelectInput>
              )}
            </Field>
            <MutationSelect defaultValue="auto" label="Nível de esterilização" hint="" />
          </div>

          <label className="flex items-start gap-3 rounded-xl border border-border bg-background/40 p-3 text-sm">
            <input
              type="checkbox"
              checked={vision}
              disabled={!catalog?.vision_ready}
              onChange={(e) => setVision(e.target.checked)}
              className="mt-0.5 size-4 accent-primary"
            />
            <span>
              <span className="flex items-center gap-2 font-medium text-foreground">
                <Eye className="size-4 text-primary" aria-hidden="true" />
                Assistir às cenas (áudio + imagem)
              </span>
              <span className="text-xs text-muted-foreground">
                {catalog?.vision_ready
                  ? "Frames do vídeo são descritos por IA multimodal — essencial em cena sem diálogo."
                  : "Precisa de uma chave Gemini ou OpenRouter em /apis."}
              </span>
            </span>
          </label>

          <label className="flex items-start gap-3 rounded-xl border border-border bg-background/40 p-3 text-sm">
            <input
              type="checkbox"
              checked={withCaptions}
              onChange={(e) => setWithCaptions(e.target.checked)}
              className="mt-0.5 size-4 accent-primary"
            />
            <span>
              <span className="font-medium text-foreground">Queimar legenda animada</span>
              <span className="block text-xs text-muted-foreground">
                Usa os presets virais do Estúdio de Legendas.
              </span>
            </span>
          </label>

          {withCaptions ? (
            <Field label="Estilo da legenda">
              {(id) => (
                <SelectInput id={id} name="caption_preset" defaultValue="hormozi">
                  {(catalog?.caption_presets ?? []).map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.label} · {preset.tag}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
          ) : null}

          <JobSettingsGuard
            busy={busy}
            disabled={blocked || (!hasFile && !card)}
            label="Gerar recap narrado"
            busyLabel="Ouvindo, assistindo e narrando…"
          />
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Envie um vídeo longo para acompanhar a transcrição, a leitura de cena, o roteiro e a montagem do recap."
          onCancel={cancel}
          onDelete={remove}
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="auto"
            actionLabel="Usar este vídeo"
            onAction={(next) => setCard(next)}
            actionBusyUrl={null}
          />
          <ToolHistory
            tool="recap"
            title="Histórico · Recap Narrado"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
