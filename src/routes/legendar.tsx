import { createFileRoute } from "@tanstack/react-router";
import { ChevronDown, ChevronUp, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, FileDrop, SelectInput, SubmitButton, TextArea } from "@/components/form";
import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import {
  ANIMATION_LABELS,
  fetchCaptionCatalog,
  type CaptionAnimation,
  type CaptionPreset,
} from "@/features/captions/api";
import { CaptionStage } from "@/features/captions/components/CaptionStage";
import { PresetGallery } from "@/features/captions/components/PresetGallery";
import {
  applyStyle,
  DEFAULT_STYLE,
  POSITION_LABEL,
  positionFromY,
  yFromPosition,
  type CaptionStyle,
} from "@/features/captions/style";
import { useCaptionDraft } from "@/features/captions/use-caption-draft";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";

export const Route = createFileRoute("/legendar")({
  head: () => ({
    meta: [
      { title: "Estúdio de Legendas Virais — editor visual estilo Canva" },
      {
        name: "description",
        content:
          "Editor visual de legendas com prévia ao vivo, posição arrastável, presets Hormozi/MrBeast/TikTok, rascunho persistente e render final esterilizado.",
      },
      { property: "og:title", content: "Estúdio de Legendas Virais" },
      {
        property: "og:description",
        content:
          "Veja a legenda antes de renderizar: arraste a posição, troque preset e assista enquanto testa.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Legendar,
});

function Legendar() {
  const { job, error, busy, run, cancel, remove } = useJobRunner("legendar");
  const { draft, hydrated, save, clear } = useCaptionDraft();

  const [presets, setPresets] = useState<CaptionPreset[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [style, setStyle] = useState<CaptionStyle>(DEFAULT_STYLE);
  const [transcript, setTranscript] = useState("");
  const [mutation, setMutation] = useState("auto");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [card, setCard] = useState<DiscoveryCard | null>(null);
  const [editorOpen, setEditorOpen] = useState(true);
  const [saved, setSaved] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const preset = presets.find((p) => p.id === style.preset) ?? presets[0] ?? null;
  const sourceLabel = file?.name ?? card?.title ?? "";

  useEffect(() => {
    const ctrl = new AbortController();
    fetchCaptionCatalog(ctrl.signal)
      .then((data) => {
        setPresets(data.presets);
        setCatalogError(null);
      })
      .catch(() => setCatalogError("Não foi possível carregar os presets do servidor."));
    return () => ctrl.abort();
  }, []);

  // Restaura o rascunho salvo (fechar e voltar a editar depois).
  useEffect(() => {
    if (!hydrated || !draft) return;
    setStyle(draft.style);
    setTranscript(draft.transcript);
    setMutation(draft.mutation || "auto");
  }, [hydrated]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function patch(next: Partial<CaptionStyle>) {
    setStyle((prev) => ({ ...prev, ...next }));
    setSaved(false);
  }

  function pickPreset(id: string) {
    const found = presets.find((p) => p.id === id);
    patch({
      preset: id,
      animation: "auto",
      uppercase: found ? found.uppercase : style.uppercase,
      wordsPerLine: found ? found.words_per_line : style.wordsPerLine,
    });
  }

  function saveDraft() {
    save({ style, transcript, mutation, sourceLabel });
    setSaved(true);
  }

  function discardDraft() {
    clear();
    setStyle(DEFAULT_STYLE);
    setTranscript("");
    setMutation("auto");
    setSaved(false);
  }

  const position = positionFromY(style.yPct);

  function buildForm(base: FormData) {
    const form = applyStyle(base, style);
    form.set("mutation", mutation);
    form.set("srt", transcript);
    return form;
  }

  function processCard(nextCard: DiscoveryCard) {
    setCard(nextCard);
    const form = buildForm(new FormData());
    form.set("url", nextCard.url);
    form.set("source_card", JSON.stringify(nextCard));
    saveDraft();
    run(() => apiPostForm<Job>("/api/legendar/run", form));
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = buildForm(new FormData());
    if (file) form.set("video", file);
    else if (card) {
      form.set("url", card.url);
      form.set("source_card", JSON.stringify(card));
    }
    saveDraft();
    run(() => apiPostForm<Job>("/api/legendar/run", form));
  }

  const draftStamp = useMemo(
    () => (draft ? new Date(draft.savedAt).toLocaleString("pt-BR") : null),
    [draft],
  );

  return (
    <ToolShell
      badge="Ferramenta 3 · /api/legendar/run"
      title="Estúdio de Legendas Virais"
      subtitle="Editor visual estilo Canva: assista o vídeo, arraste a legenda para onde quiser, troque o preset e veja a animação ao vivo antes de queimar. O render final acontece no FFmpeg do aaPanel com esterilização na mesma passada."
      left={
        <form ref={formRef} onSubmit={onSubmit} className="space-y-5">
          <Field label="Vídeo de entrada" hint="MP4, MOV ou MKV — até 500 MB.">
            {(id) => (
              <FileDrop
                id={id}
                name="video"
                accept="video/mp4,video/quicktime,video/x-matroska"
                hint="MP4 / MOV / MKV"
                onSelect={(f) => {
                  setFile(f ?? null);
                  if (f) setCard(null);
                }}
              />
            )}
          </Field>

          <div className="rounded-2xl border border-border/70 bg-background/40 p-3 sm:p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground">Editor de legenda</p>
                <p className="truncate text-xs text-muted-foreground">
                  {sourceLabel || "Prévia simulada — arraste a legenda no palco"}
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={saveDraft}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs text-foreground transition hover:border-primary/60"
                >
                  <Save className="size-3.5" />
                  {saved ? "Salvo" : "Salvar rascunho"}
                </button>
                <button
                  type="button"
                  onClick={() => setEditorOpen((v) => !v)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs text-foreground transition hover:border-primary/60"
                >
                  {editorOpen ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                  {editorOpen ? "Fechar" : "Reabrir"}
                </button>
                {draft ? (
                  <button
                    type="button"
                    onClick={discardDraft}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-destructive/40 px-2.5 py-1.5 text-xs text-destructive transition hover:bg-destructive/10"
                  >
                    <Trash2 className="size-3.5" />
                    Excluir
                  </button>
                ) : null}
              </div>
            </div>

            {draftStamp ? (
              <p className="mt-2 text-[11px] text-muted-foreground">
                Rascunho salvo em {draftStamp} — volte quando quiser para continuar editando.
              </p>
            ) : null}

            {editorOpen ? (
              <div className="mt-4">
                <CaptionStage
                  src={previewUrl}
                  poster={card?.thumbnail ?? null}
                  style={style}
                  preset={preset}
                  transcript={transcript}
                  onYChange={(y) => patch({ yPct: y })}
                />
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-sm font-medium text-foreground">Preset viral</p>
              {preset ? <span className="text-xs text-muted-foreground">{preset.label}</span> : null}
            </div>
            {catalogError ? (
              <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                {catalogError}
              </p>
            ) : presets.length === 0 ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {[0, 1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-44 animate-pulse rounded-2xl bg-muted/50" />
                ))}
              </div>
            ) : (
              <PresetGallery presets={presets} value={style.preset} onChange={pickPreset} />
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Animação">
              {(id) => (
                <SelectInput
                  id={id}
                  value={style.animation}
                  onChange={(e) => patch({ animation: e.target.value as CaptionAnimation })}
                >
                  {(Object.keys(ANIMATION_LABELS) as CaptionAnimation[]).map((key) => (
                    <option key={key} value={key}>
                      {ANIMATION_LABELS[key]}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field
              label="Posição"
              hint={`Arraste no palco para o ajuste fino · atual ${style.yPct}%`}
            >
              {(id) => (
                <SelectInput
                  id={id}
                  value={position}
                  onChange={(e) =>
                    patch({ yPct: yFromPosition(e.target.value as "top" | "center" | "bottom") })
                  }
                >
                  {(["top", "center", "bottom"] as const).map((p) => (
                    <option key={p} value={p}>
                      {POSITION_LABEL[p]}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field
              label={`Palavras por bloco · ${style.wordsPerLine}`}
              hint="1–3 palavras = retenção máxima. 6+ = leitura de podcast."
            >
              {(id) => (
                <input
                  id={id}
                  type="range"
                  min={1}
                  max={10}
                  step={1}
                  value={style.wordsPerLine}
                  onChange={(e) => patch({ wordsPerLine: Number(e.target.value) })}
                  className="w-full accent-primary"
                />
              )}
            </Field>
            <Field label={`Tamanho da fonte · ${style.fontScale.toFixed(2)}x`}>
              {(id) => (
                <input
                  id={id}
                  type="range"
                  min={0.6}
                  max={1.8}
                  step={0.05}
                  value={style.fontScale}
                  onChange={(e) => patch({ fontScale: Number(e.target.value) })}
                  className="w-full accent-primary"
                />
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-3 rounded-2xl border border-border/60 p-3 sm:grid-cols-2 sm:items-center xl:grid-cols-4">
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={style.uppercase}
                onChange={(e) => patch({ uppercase: e.target.checked })}
                className="size-4 accent-primary"
              />
              CAIXA ALTA
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={style.emoji}
                onChange={(e) => patch({ emoji: e.target.checked })}
                className="size-4 accent-primary"
              />
              Emojis contextuais
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="color"
                value={style.accent || preset?.preview.accent || "#ffe500"}
                onChange={(e) => patch({ accent: e.target.value })}
                className="h-9 w-12 cursor-pointer rounded-lg border border-input bg-transparent"
                aria-label="Cor de destaque"
              />
              Destaque
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="color"
                value={style.primary || preset?.preview.color || "#ffffff"}
                onChange={(e) => patch({ primary: e.target.value })}
                className="h-9 w-12 cursor-pointer rounded-lg border border-input bg-transparent"
                aria-label="Cor do texto"
              />
              Texto
            </label>
          </div>

          <MutationSelect value={mutation} onChange={setMutation} />

          <Field
            label="Transcrição (opcional)"
            hint="Deixe vazio para transcrição automática com timestamps por palavra. Aceita texto simples ou SRT — o texto colado também alimenta a prévia do editor."
          >
            {(id) => (
              <TextArea
                id={id}
                value={transcript}
                onChange={(e) => {
                  setTranscript(e.target.value);
                  setSaved(false);
                }}
                placeholder={"1\n00:00:00,000 --> 00:00:02,000\nSeu texto"}
              />
            )}
          </Field>

          <SubmitButton busy={busy} disabled={!file && !card}>
            {busy ? "Renderizando legendas…" : "Gerar vídeo legendado"}
          </SubmitButton>
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Ajuste a legenda no editor, depois gere o vídeo para acompanhar aqui o progresso e baixar o resultado."
          onCancel={cancel}
          onDelete={remove}
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="auto"
            actionLabel="Legendar este vídeo"
            onAction={processCard}
            actionBusyUrl={busy ? card?.url ?? null : null}
          />
          <ToolHistory
            tool="legendar"
            title="Histórico · Legendas"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
