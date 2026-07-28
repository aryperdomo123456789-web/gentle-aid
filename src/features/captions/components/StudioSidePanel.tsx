import { X } from "lucide-react";

import { DiscoveryPanel } from "@/components/DiscoveryPanel";
import { Field, FileDrop, TextArea } from "@/components/form";
import { JobSettingsGuard } from "@/components/JobSettingsGuard";
import { MutationSelect } from "@/components/MutationSelect";
import { AnimationPanel } from "@/features/captions/components/AnimationPanel";
import { PresetGallery } from "@/features/captions/components/PresetGallery";
import { panelLabel, type PanelId } from "@/features/captions/panels";
import type { CaptionStudio } from "@/features/captions/use-caption-studio";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";

/** Painel contextual do rail — um bloco por ferramenta selecionada. */
export function StudioSidePanel({ studio, panel }: { studio: CaptionStudio; panel: PanelId }) {
  return (
    <aside
      aria-label="Painel de edição"
      className="absolute inset-0 z-30 w-full overflow-y-auto overscroll-contain border-border bg-card p-3 shadow-xl md:static md:inset-auto md:z-auto md:w-[300px] md:border-r md:shadow-none lg:w-[340px] xl:w-[360px]"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-foreground">{panelLabel(panel)}</p>
        <button
          type="button"
          onClick={() => studio.setPanel(null)}
          className="grid size-7 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
          aria-label="Fechar painel"
        >
          <X className="size-4" />
        </button>
      </div>

      <PanelBody studio={studio} panel={panel} />
    </aside>
  );
}

function PanelBody({ studio, panel }: { studio: CaptionStudio; panel: PanelId }) {
  const { style, patch, preset, presets, catalogError, busy, card, job } = studio;

  switch (panel) {
    case "uploads":
      return (
        <div className="space-y-4">
          <Field label="Vídeo de entrada" hint="MP4, MOV ou MKV — até 500 MB.">
            {(id) => (
              <FileDrop
                id={id}
                name="video"
                accept="video/mp4,video/quicktime,video/x-matroska"
                hint="MP4 / MOV / MKV"
                onSelect={(f) => studio.pickFile(f ?? null)}
              />
            )}
          </Field>
          {card ? (
            <p className="rounded-xl border border-border/60 bg-background/40 p-3 text-xs text-muted-foreground">
              Mídia da pesquisa selecionada: <strong>{card.title}</strong>
            </p>
          ) : null}
        </div>
      );

    case "pesquisa":
      return (
        <DiscoveryPanel
          defaultPlatform="auto"
          actionLabel="Legendar este vídeo"
          onAction={studio.processCard}
          actionBusyUrl={busy ? (card?.url ?? null) : null}
        />
      );

    case "estilos":
      if (catalogError) {
        return (
          <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
            {catalogError}
          </p>
        );
      }
      if (presets.length === 0) {
        return (
          <div className="grid gap-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-40 animate-pulse rounded-2xl bg-muted/50" />
            ))}
          </div>
        );
      }
      return <PresetGallery presets={presets} value={style.preset} onChange={studio.pickPreset} />;

    case "texto":
      return (
        <div className="space-y-4">
          <Field
            label="Transcrição (opcional)"
            hint="Vazio = transcrição automática por palavra. Aceita texto simples ou SRT — o texto colado alimenta a prévia."
          >
            {(id) => (
              <TextArea
                id={id}
                value={studio.transcript}
                onChange={(e) => studio.changeTranscript(e.target.value)}
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
      );

    case "animacao":
      return <AnimationPanel studio={studio} />;

    case "cores":
      return (
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
      );

    case "esterilizar":
      return <MutationSelect value={studio.mutation} onChange={studio.setMutation} />;

    case "exportar":
      return (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Confira o resumo e salve as configurações. A renderização só libera depois da
            conferência.
          </p>
          <JobSettingsGuard
            busy={busy}
            disabled={!studio.file && !card}
            entries={studio.exportEntries}
            signature={studio.exportSignature}
            onStart={studio.exportVideo}
            label="Exportar legendado"
            busyLabel="Renderizando…"
          />
          {!studio.file && !card ? (
            <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200">
              Envie um vídeo em Uploads ou escolha um na Pesquisa antes de exportar.
            </p>
          ) : null}
        </div>
      );

    case "jobs":
      return (
        <StatusPanel
          job={job}
          error={studio.error}
          busy={busy}
          emptyHint="Ajuste a legenda no palco e clique em Exportar legendado para acompanhar aqui."
          onCancel={studio.cancel}
          onDelete={studio.remove}
        />
      );

    case "historico":
      return (
        <ToolHistory
          tool="legendar"
          title="Histórico · Legendas"
          refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
        />
      );

    default:
      return null;
  }
}
