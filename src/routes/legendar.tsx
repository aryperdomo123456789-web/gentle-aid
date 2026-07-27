import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

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
import { PresetGallery } from "@/features/captions/components/PresetGallery";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, type Job } from "@/lib/api";

export const Route = createFileRoute("/legendar")({
  head: () => ({
    meta: [
      { title: "Estúdio de Legendas Virais — karaokê palavra a palavra" },
      {
        name: "description",
        content:
          "Legendas virais palavra a palavra com presets Hormozi, MrBeast, TikTok e karaokê musical. Transcrição automática, animação ASS e esterilização na mesma passada.",
      },
      { property: "og:title", content: "Estúdio de Legendas Virais" },
      {
        property: "og:description",
        content:
          "Presets de legenda que dominam Reels, Shorts e TikTok — karaokê, pop palavra a palavra e highlight box.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Legendar,
});

const DEFAULT_PRESET = "hormozi";

function Legendar() {
  const { job, error, busy, run, cancel, remove } = useJobRunner("legendar");
  const [hasFile, setHasFile] = useState(false);
  const [pickedUrl, setPickedUrl] = useState<string | null>(null);
  const [presets, setPresets] = useState<CaptionPreset[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [presetId, setPresetId] = useState(DEFAULT_PRESET);
  const [animation, setAnimation] = useState<CaptionAnimation>("auto");
  const [position, setPosition] = useState("bottom");
  const [wordsPerLine, setWordsPerLine] = useState(3);
  const [fontScale, setFontScale] = useState(1);
  const [uppercase, setUppercase] = useState(true);
  const [emoji, setEmoji] = useState(false);
  const [accent, setAccent] = useState("");
  const formRef = useRef<HTMLFormElement>(null);

  const preset = presets.find((p) => p.id === presetId) ?? null;

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
    if (!preset) return;
    setUppercase(preset.uppercase);
    setWordsPerLine(preset.words_per_line);
    setAnimation("auto");
  }, [preset?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function buildForm(base: FormData) {
    base.set("preset", presetId);
    base.set("animation", animation);
    base.set("position", position);
    base.set("words_per_line", String(wordsPerLine));
    base.set("font_scale", fontScale.toFixed(2));
    base.set("uppercase", uppercase ? "1" : "0");
    base.set("emoji", emoji ? "1" : "0");
    if (accent) base.set("accent", accent);
    return base;
  }

  function processCard(card: DiscoveryCard) {
    const form = buildForm(formRef.current ? new FormData(formRef.current) : new FormData());
    form.delete("video");
    form.delete("audio");
    form.set("url", card.url);
    form.set("source_card", JSON.stringify(card));
    setPickedUrl(card.url);
    run(() => apiPostForm<Job>("/api/legendar/run", form));
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = buildForm(new FormData(e.currentTarget));
    run(() => apiPostForm<Job>("/api/legendar/run", form));
  }

  return (
    <ToolShell
      badge="Ferramenta 3 · /api/legendar/run"
      title="Estúdio de Legendas Virais"
      subtitle="Legendas palavra a palavra com os presets que dominam Reels, Shorts e TikTok. Transcrição automática com timestamps, renderização ASS animada e esterilização do vídeo na mesma passada do FFmpeg."
      left={
        <form ref={formRef} onSubmit={onSubmit} className="space-y-5">
          <Field label="Vídeo de entrada" hint="MP4, MOV ou MKV — até 500 MB.">
            {(id) => (
              <FileDrop
                id={id}
                name="video"
                accept="video/mp4,video/quicktime,video/x-matroska"
                hint="MP4 / MOV / MKV"
                onSelect={(f) => setHasFile(Boolean(f))}
              />
            )}
          </Field>

          <div className="space-y-3">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-sm font-medium text-foreground">Preset viral</p>
              {preset ? (
                <span className="text-xs text-muted-foreground">{preset.label}</span>
              ) : null}
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
              <PresetGallery presets={presets} value={presetId} onChange={setPresetId} />
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Animação">
              {(id) => (
                <SelectInput
                  id={id}
                  value={animation}
                  onChange={(e) => setAnimation(e.target.value as CaptionAnimation)}
                >
                  {(Object.keys(ANIMATION_LABELS) as CaptionAnimation[]).map((key) => (
                    <option key={key} value={key}>
                      {ANIMATION_LABELS[key]}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field label="Posição">
              {(id) => (
                <SelectInput
                  id={id}
                  value={position}
                  onChange={(e) => setPosition(e.target.value)}
                >
                  <option value="bottom">Inferior (safe area)</option>
                  <option value="center">Centro</option>
                  <option value="top">Superior</option>
                </SelectInput>
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field
              label={`Palavras por bloco · ${wordsPerLine}`}
              hint="1–3 palavras = retenção máxima. 6+ = leitura de podcast."
            >
              {(id) => (
                <input
                  id={id}
                  type="range"
                  min={1}
                  max={10}
                  step={1}
                  value={wordsPerLine}
                  onChange={(e) => setWordsPerLine(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              )}
            </Field>
            <Field label={`Tamanho da fonte · ${fontScale.toFixed(2)}x`}>
              {(id) => (
                <input
                  id={id}
                  type="range"
                  min={0.6}
                  max={1.8}
                  step={0.05}
                  value={fontScale}
                  onChange={(e) => setFontScale(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-3 rounded-2xl border border-border/60 p-3 sm:grid-cols-3 sm:items-center">
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={uppercase}
                onChange={(e) => setUppercase(e.target.checked)}
                className="size-4 accent-primary"
              />
              CAIXA ALTA
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={emoji}
                onChange={(e) => setEmoji(e.target.checked)}
                className="size-4 accent-primary"
              />
              Emojis contextuais
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="color"
                value={accent || "#ffe500"}
                onChange={(e) => setAccent(e.target.value)}
                className="h-9 w-12 cursor-pointer rounded-lg border border-input bg-transparent"
                aria-label="Cor de destaque"
              />
              Cor de destaque
            </label>
          </div>

          <MutationSelect defaultValue="auto" />

          <Field
            label="Transcrição (opcional)"
            hint="Deixe vazio para transcrição automática com timestamps por palavra. Aceita texto simples ou SRT."
          >
            {(id) => (
              <TextArea
                id={id}
                name="srt"
                placeholder={"1\n00:00:00,000 --> 00:00:02,000\nSeu texto"}
              />
            )}
          </Field>

          <SubmitButton busy={busy} disabled={!hasFile}>
            {busy ? "Renderizando legendas…" : "Gerar vídeo legendado"}
          </SubmitButton>
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Envie um vídeo ou escolha um da pesquisa para acompanhar a renderização das legendas."
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
            actionBusyUrl={busy ? pickedUrl : null}
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
