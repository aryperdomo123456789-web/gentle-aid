import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ChevronLeft,
  Clock3,
  Home,
  Image as ImageIcon,
  Palette,
  Redo2,
  Save,
  Search,
  Shield,
  Sparkles,
  Trash2,
  Type,
  Undo2,
  Upload,
  Wand2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, FileDrop, SelectInput, TextArea } from "@/components/form";
import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import {
  ANIMATION_LABELS,
  fetchCaptionCatalog,
  type CaptionAnimation,
  type CaptionPreset,
} from "@/features/captions/api";
import { CaptionStage, type CaptionStageApi } from "@/features/captions/components/CaptionStage";
import { EditorTimeline } from "@/features/captions/components/EditorTimeline";
import { PresetGallery } from "@/features/captions/components/PresetGallery";
import {
  applyStyle,
  ASPECT_LABEL,
  DEFAULT_STYLE,
  POSITION_LABEL,
  positionFromY,
  yFromPosition,
  type CaptionAspect,
  type CaptionStyle,
} from "@/features/captions/style";
import { useCaptionDraft } from "@/features/captions/use-caption-draft";
import { buildWords, groupWords } from "@/features/captions/timeline";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/legendar")({
  head: () => ({
    meta: [
      { title: "Estúdio de Legendas Virais — editor visual estilo Canva" },
      {
        name: "description",
        content:
          "Editor visual de legendas com painel lateral, palco com prévia ao vivo, linha do tempo por bloco e render final esterilizado no aaPanel.",
      },
      { property: "og:title", content: "Estúdio de Legendas Virais" },
      {
        property: "og:description",
        content:
          "Fluxo idêntico ao Canva: menu lateral de ferramentas, palco central, timeline embaixo e exportação legendada.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Legendar,
});

type PanelId =
  | "uploads"
  | "pesquisa"
  | "estilos"
  | "texto"
  | "animacao"
  | "cores"
  | "esterilizar"
  | "exportar"
  | "jobs"
  | "historico";

const RAIL: { id: PanelId; label: string; icon: typeof Upload }[] = [
  { id: "uploads", label: "Uploads", icon: Upload },
  { id: "pesquisa", label: "Pesquisar", icon: Search },
  { id: "estilos", label: "Estilos", icon: Sparkles },
  { id: "texto", label: "Texto", icon: Type },
  { id: "animacao", label: "Animação", icon: Wand2 },
  { id: "cores", label: "Cores", icon: Palette },
  { id: "esterilizar", label: "Esterilizar", icon: Shield },
  { id: "exportar", label: "Exportar", icon: ShieldCheck },
  { id: "jobs", label: "Job", icon: ImageIcon },
  { id: "historico", label: "Histórico", icon: Clock3 },
];

function Legendar() {
  const { job, error, busy, run, cancel, remove } = useJobRunner("legendar");
  const { draft, hydrated, save, clear } = useCaptionDraft();

  const [presets, setPresets] = useState<CaptionPreset[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [style, setStyle] = useState<CaptionStyle>(DEFAULT_STYLE);
  const [history, setHistory] = useState<CaptionStyle[]>([DEFAULT_STYLE]);
  const [cursor, setCursor] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [mutation, setMutation] = useState("auto");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [card, setCard] = useState<DiscoveryCard | null>(null);
  const [panel, setPanel] = useState<PanelId | null>("uploads");
  const [saved, setSaved] = useState(false);
  const [clock, setClock] = useState({ time: 0, duration: 12, playing: false });
  const [zoom, setZoom] = useState(1);
  const [detected, setDetected] = useState<Exclude<CaptionAspect, "auto"> | null>(null);
  const stageApi = useRef<CaptionStageApi | null>(null);

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

  useEffect(() => {
    if (!hydrated || !draft) return;
    setStyle(draft.style);
    setHistory([draft.style]);
    setCursor(0);
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
    setStyle((prev) => {
      const merged = { ...prev, ...next };
      setHistory((h) => [...h.slice(0, cursor + 1), merged].slice(-40));
      setCursor((c) => Math.min(c + 1, 39));
      return merged;
    });
    setSaved(false);
  }

  function undo() {
    if (cursor <= 0) return;
    setCursor(cursor - 1);
    setStyle(history[cursor - 1]);
  }

  function redo() {
    if (cursor >= history.length - 1) return;
    setCursor(cursor + 1);
    setStyle(history[cursor + 1]);
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
    setHistory([DEFAULT_STYLE]);
    setCursor(0);
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

  /** Nada roda direto: a mídia é carregada e a exportação exige confirmação. */
  function processCard(nextCard: DiscoveryCard) {
    setCard(nextCard);
    setFile(null);
    saveDraft();
    setPanel("exportar");
  }

  function exportVideo() {
    if (!file && !card) {
      setPanel("uploads");
      return;
    }
    const form = buildForm(new FormData());
    if (file) form.set("video", file);
    else if (card) {
      form.set("url", card.url);
      form.set("source_card", JSON.stringify(card));
    }
    saveDraft();
    setPanel("jobs");
    run(() => apiPostForm<Job>("/api/legendar/run", form));
  }

  const draftStamp = useMemo(
    () => (draft ? new Date(draft.savedAt).toLocaleString("pt-BR") : null),
    [draft],
  );

  const blocks = useMemo(
    () => groupWords(buildWords(transcript, clock.duration), style.wordsPerLine),
    [transcript, clock.duration, style.wordsPerLine],
  );

  const onTick = useCallback((time: number, duration: number, playing: boolean) => {
    setClock((prev) =>
      prev.time === time && prev.duration === duration && prev.playing === playing
        ? prev
        : { time, duration, playing },
    );
  }, []);

  const onReady = useCallback((api: CaptionStageApi) => {
    stageApi.current = api;
  }, []);

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-background">
      {/* ===== Barra superior (Arquivo / Edição / Exportar) ===== */}
      <header className="flex h-14 shrink-0 items-center gap-1 border-b border-border bg-card px-2 sm:gap-2 sm:px-3">
        <Link
          to="/"
          className="grid size-9 shrink-0 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
          aria-label="Voltar ao início"
        >
          <Home className="size-4" />
        </Link>
        <button
          type="button"
          onClick={saveDraft}
          className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-foreground transition hover:bg-muted sm:inline-flex"
        >
          <Save className="size-4" />
          {saved ? "Salvo" : "Arquivo"}
        </button>
        <button
          type="button"
          onClick={discardDraft}
          className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-foreground transition hover:bg-muted md:inline-flex"
        >
          <Trash2 className="size-4" />
          Descartar
        </button>
        <span className="mx-1 hidden h-6 w-px bg-border sm:block" />
        <button
          type="button"
          onClick={undo}
          disabled={cursor <= 0}
          className="grid size-9 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:opacity-40"
          aria-label="Desfazer"
        >
          <Undo2 className="size-4" />
        </button>
        <button
          type="button"
          onClick={redo}
          disabled={cursor >= history.length - 1}
          className="grid size-9 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:opacity-40"
          aria-label="Refazer"
        >
          <Redo2 className="size-4" />
        </button>

        <p className="mx-auto hidden min-w-0 truncate px-2 text-sm text-muted-foreground lg:block">
          {sourceLabel || "Estúdio de Legendas Virais"}
          {draftStamp ? ` · rascunho ${draftStamp}` : ""}
        </p>

        <div className="ml-auto flex shrink-0 items-center gap-1.5 lg:ml-0">
          <span className="hidden rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground xl:inline">
            {preset?.label ?? "preset"} · {POSITION_LABEL[position]} · {style.yPct}%
          </span>
          <button
            type="button"
            onClick={exportVideo}
            disabled={busy}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-60 sm:px-4"
          >
            <span className="sm:hidden">{busy ? "…" : "Exportar"}</span>
            <span className="hidden sm:inline">{busy ? "Renderizando…" : "Exportar legendado"}</span>
          </button>
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1 flex-col md:flex-row">
        {/* ===== Rail lateral de ferramentas ===== */}
        <nav
          aria-label="Ferramentas"
          className="scroll-x flex shrink-0 gap-1 overflow-x-auto border-b border-border bg-card px-1 py-1 md:w-16 md:flex-col md:items-center md:overflow-x-visible md:overflow-y-auto md:border-b-0 md:border-r md:px-0 md:py-2 lg:w-[74px]"
        >
          {RAIL.map((item) => {
            const Icon = item.icon;
            const active = panel === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setPanel(active ? null : item.id)}
                aria-pressed={active}
                className={cn(
                  "flex min-h-14 w-16 shrink-0 flex-col items-center justify-center gap-1 rounded-lg px-1 py-2 text-[10px] leading-tight transition md:w-full",
                  active
                    ? "bg-primary/15 text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Icon className={cn("size-5", active && "text-primary")} />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="relative flex min-h-0 flex-1 md:contents">
        {/* ===== Painel contextual ===== */}
        {panel ? (

          <aside
            aria-label="Painel de edição"
            className="absolute inset-0 z-30 w-full overflow-y-auto overscroll-contain border-border bg-card p-3 shadow-xl md:static md:inset-auto md:z-auto md:w-[300px] md:border-r md:shadow-none lg:w-[340px] xl:w-[360px]"
          >

            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-foreground">
                {RAIL.find((r) => r.id === panel)?.label}
              </p>
              <button
                type="button"
                onClick={() => setPanel(null)}
                className="grid size-7 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                aria-label="Fechar painel"
              >
                <X className="size-4" />
              </button>
            </div>

            {panel === "uploads" ? (
              <div className="space-y-4">
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
                {card ? (
                  <p className="rounded-xl border border-border/60 bg-background/40 p-3 text-xs text-muted-foreground">
                    Mídia da pesquisa selecionada: <strong>{card.title}</strong>
                  </p>
                ) : null}
              </div>
            ) : null}

            {panel === "pesquisa" ? (
              <DiscoveryPanel
                defaultPlatform="auto"
                actionLabel="Legendar este vídeo"
                onAction={processCard}
                actionBusyUrl={busy ? card?.url ?? null : null}
              />
            ) : null}

            {panel === "estilos" ? (
              catalogError ? (
                <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
                  {catalogError}
                </p>
              ) : presets.length === 0 ? (
                <div className="grid gap-3">
                  {[0, 1, 2, 3].map((i) => (
                    <div key={i} className="h-40 animate-pulse rounded-2xl bg-muted/50" />
                  ))}
                </div>
              ) : (
                <PresetGallery presets={presets} value={style.preset} onChange={pickPreset} />
              )
            ) : null}

            {panel === "texto" ? (
              <div className="space-y-4">
                <Field
                  label="Transcrição (opcional)"
                  hint="Vazio = transcrição automática por palavra. Aceita texto simples ou SRT — o texto colado alimenta a prévia."
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
              </div>
            ) : null}

            {panel === "animacao" ? (
              <div className="space-y-4">
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
                <label className="flex items-start gap-2 rounded-xl border border-border/60 bg-muted/20 p-3 text-sm text-foreground">
                  <input
                    type="checkbox"
                    checked={style.beatSync}
                    onChange={(e) => patch({ beatSync: e.target.checked })}
                    className="mt-0.5 size-4 accent-primary"
                  />
                  <span>
                    Legenda no ritmo da música
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      O servidor analisa a trilha do vídeo, detecta o BPM e encaixa cada palavra na batida.
                      Combina com a animação “Beat”.
                    </span>
                  </span>
                </label>
                <Field label="Posição" hint={`Arraste no palco para ajuste fino · atual ${style.yPct}%`}>
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
                <Field
                  label={`Palavras por bloco · ${style.wordsPerLine}`}
                  hint="1–3 palavras = retenção máxima."
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
                <Field
                  label={`Tamanho da fonte · ${style.fontScale.toFixed(2)}x`}
                  hint="Arraste para a esquerda para deixar a legenda menor e mais discreta."
                >
                  {(id) => (
                    <input
                      id={id}
                      type="range"
                      min={0.35}
                      max={1.8}
                      step={0.05}
                      value={style.fontScale}
                      onChange={(e) => patch({ fontScale: Number(e.target.value) })}
                      className="w-full accent-primary"
                    />
                  )}
                </Field>
                <div className="flex flex-wrap gap-2">
                  {[
                    { label: "Pequena", value: 0.6 },
                    { label: "Média", value: 1 },
                    { label: "Grande", value: 1.4 },
                  ].map((opt) => (
                    <button
                      key={opt.label}
                      type="button"
                      onClick={() => patch({ fontScale: opt.value })}
                      className={cn(
                        "rounded-lg border px-3 py-1.5 text-xs transition",
                        Math.abs(style.fontScale - opt.value) < 0.03
                          ? "border-primary bg-primary/15 text-foreground"
                          : "border-border text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                <Field
                  label="Formato do vídeo"
                  hint={
                    style.aspect === "auto"
                      ? `Detectado automaticamente: ${detected ?? "aguardando o vídeo"}`
                      : "Formato fixado manualmente para a prévia."
                  }
                >
                  {(id) => (
                    <SelectInput
                      id={id}
                      value={style.aspect}
                      onChange={(e) => patch({ aspect: e.target.value as CaptionAspect })}
                    >
                      {(Object.keys(ASPECT_LABEL) as CaptionAspect[]).map((key) => (
                        <option key={key} value={key}>
                          {ASPECT_LABEL[key]}
                        </option>
                      ))}
                    </SelectInput>
                  )}
                </Field>
              </div>
            ) : null}

            {panel === "cores" ? (
              <div className="space-y-4">
                <label className="flex items-center justify-between gap-3 rounded-xl border border-border/60 p-3 text-sm text-foreground">
                  Cor de destaque
                  <input
                    type="color"
                    value={style.accent || preset?.preview.accent || "#ffe500"}
                    onChange={(e) => patch({ accent: e.target.value })}
                    className="h-9 w-14 cursor-pointer rounded-lg border border-input bg-transparent"
                  />
                </label>
                <label className="flex items-center justify-between gap-3 rounded-xl border border-border/60 p-3 text-sm text-foreground">
                  Cor do texto
                  <input
                    type="color"
                    value={style.primary || preset?.preview.color || "#ffffff"}
                    onChange={(e) => patch({ primary: e.target.value })}
                    className="h-9 w-14 cursor-pointer rounded-lg border border-input bg-transparent"
                  />
                </label>
                <button
                  type="button"
                  onClick={() => patch({ accent: "", primary: "" })}
                  className="w-full rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground transition hover:text-foreground"
                >
                  Voltar às cores do preset
                </button>
              </div>
            ) : null}

            {panel === "esterilizar" ? (
              <MutationSelect value={mutation} onChange={setMutation} />
            ) : null}

            {panel === "jobs" ? (
              <StatusPanel
                job={job}
                error={error}
                busy={busy}
                emptyHint="Ajuste a legenda no palco e clique em Exportar legendado para acompanhar aqui."
                onCancel={cancel}
                onDelete={remove}
              />
            ) : null}

            {panel === "historico" ? (
              <ToolHistory
                tool="legendar"
                title="Histórico · Legendas"
                refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
              />
            ) : null}
          </aside>
        ) : (
          <button
            type="button"
            onClick={() => setPanel("estilos")}
            className="hidden w-4 shrink-0 items-center justify-center border-r border-border bg-card text-muted-foreground transition hover:text-foreground md:flex"
            aria-label="Abrir painel"
          >
            <ChevronLeft className="size-3 rotate-180" />
          </button>
        )}

        {/* ===== Palco + timeline ===== */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-border/60 bg-card/40 px-3 py-1.5">
            <span className="mr-1 text-[11px] uppercase tracking-wide text-muted-foreground">
              Formato
            </span>
            {(["auto", "9:16", "16:9", "1:1"] as CaptionAspect[]).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => patch({ aspect: opt })}
                title={ASPECT_LABEL[opt]}
                className={cn(
                  "rounded-lg border px-2.5 py-1 text-[11px] transition",
                  style.aspect === opt
                    ? "border-primary bg-primary/15 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {opt === "auto" ? `Auto${detected ? ` · ${detected}` : ""}` : opt}
              </button>
            ))}
            <div className="ml-auto flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground">Legenda</span>
              <input
                type="range"
                min={0.35}
                max={1.8}
                step={0.05}
                value={style.fontScale}
                onChange={(e) => patch({ fontScale: Number(e.target.value) })}
                className="w-24 accent-primary sm:w-36"
                aria-label="Tamanho da legenda"
              />
              <span className="w-10 shrink-0 font-mono text-[11px] text-muted-foreground">
                {style.fontScale.toFixed(2)}x
              </span>
            </div>
          </div>
          <div className="flex min-h-0 flex-1 items-center justify-center overflow-hidden bg-muted/30 p-3 sm:p-6">
            <CaptionStage
              className="flex h-full min-h-0 w-full items-center justify-center"
              src={previewUrl}
              poster={card?.thumbnail ?? null}
              style={style}
              preset={preset}
              transcript={transcript}
              onYChange={(y) => patch({ yPct: y })}
              onTick={onTick}
              onReady={onReady}
              onDetectAspect={setDetected}
              hideControls
            />
          </div>


          <EditorTimeline
            duration={clock.duration}
            time={clock.time}
            playing={clock.playing}
            blocks={blocks}
            uppercase={style.uppercase}
            sourceLabel={sourceLabel}
            poster={card?.thumbnail ?? null}
            zoom={zoom}
            onZoom={setZoom}
            onSeek={(t) => stageApi.current?.seek(t)}
            onToggle={() => stageApi.current?.toggle()}
          />
        </div>
        </div>
      </div>

    </div>
  );
}
