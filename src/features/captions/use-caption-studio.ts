import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { DiscoveryCard } from "@/components/DiscoveryPanel";
import {
  fetchCaptionCatalog,
  type CaptionPreset,
} from "@/features/captions/api";
import type { CaptionStageApi } from "@/features/captions/components/CaptionStage";
import {
  applyStyle,
  ASPECT_LABEL,
  DEFAULT_STYLE,
  POSITION_LABEL,
  positionFromY,
  type CaptionAspect,
  type CaptionStyle,
} from "@/features/captions/style";
import { buildWords, groupWords } from "@/features/captions/timeline";
import { useCaptionDraft } from "@/features/captions/use-caption-draft";
import type { PanelId } from "@/features/captions/panels";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";

const HISTORY_LIMIT = 40;

/**
 * Estado e regras do Estúdio de Legendas.
 *
 * A rota `/legendar` só monta a interface: undo/redo, rascunho, catálogo de
 * presets, montagem do formulário e disparo do job moram aqui.
 */
export function useCaptionStudio() {
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
  const position = positionFromY(style.yPct);

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
      setHistory((h) => [...h.slice(0, cursor + 1), merged].slice(-HISTORY_LIMIT));
      setCursor((c) => Math.min(c + 1, HISTORY_LIMIT - 1));
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

  function changeTranscript(value: string) {
    setTranscript(value);
    setSaved(false);
  }

  function pickFile(next: File | null) {
    setFile(next);
    if (next) setCard(null);
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
    const form = applyStyle(new FormData(), style);
    form.set("mutation", mutation);
    form.set("srt", transcript);
    if (file) form.set("video", file);
    else if (card) {
      form.set("url", card.url);
      form.set("source_card", JSON.stringify(card));
    }
    saveDraft();
    setPanel("jobs");
    run(() => apiPostForm<Job>("/api/legendar/run", form));
  }

  /** Resumo legível do que vai para o servidor — usado pela trava de segurança. */
  const exportEntries = useMemo(() => {
    const source = file
      ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`
      : card
        ? card.title
        : "nenhuma mídia";
    const words = transcript.trim() ? `${transcript.trim().split(/\s+/).length} palavras` : "vazio";
    return [
      { name: "source", label: "Mídia de origem", value: source },
      { name: "preset", label: "Preset de legenda", value: preset?.label ?? style.preset },
      { name: "aspect", label: "Formato", value: ASPECT_LABEL[style.aspect] ?? style.aspect },
      { name: "position", label: "Posição", value: `${POSITION_LABEL[position]} · ${style.yPct}%` },
      { name: "fontScale", label: "Tamanho da fonte", value: `${style.fontScale.toFixed(2)}x` },
      { name: "wordsPerLine", label: "Palavras por linha", value: String(style.wordsPerLine) },
      { name: "transcript", label: "Roteiro/legenda", value: words },
      { name: "mutation", label: "Esterilização", value: mutation },
    ];
  }, [file, card, preset, style, position, transcript, mutation]);

  const exportSignature = useMemo(() => JSON.stringify([exportEntries]), [exportEntries]);

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

  return {
    // job
    job,
    error,
    busy,
    cancel,
    remove,
    // catálogo
    presets,
    preset,
    catalogError,
    // estilo e edição
    style,
    patch,
    pickPreset,
    position,
    detected,
    setDetected,
    canUndo: cursor > 0,
    canRedo: cursor < history.length - 1,
    undo,
    redo,
    // conteúdo
    transcript,
    changeTranscript,
    mutation,
    setMutation,
    file,
    pickFile,
    card,
    previewUrl,
    sourceLabel,
    // rascunho
    saved,
    saveDraft,
    discardDraft,
    draftStamp,
    // painel e palco
    panel,
    setPanel,
    clock,
    blocks,
    zoom,
    setZoom,
    stageApi,
    onTick,
    onReady,
    // exportação
    exportEntries,
    exportSignature,
    exportVideo,
    processCard,
  };
}

export type CaptionStudio = ReturnType<typeof useCaptionStudio>;
