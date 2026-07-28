import { Home, Redo2, Save, Trash2, Undo2 } from "lucide-react";
import { Link } from "@tanstack/react-router";

import { POSITION_LABEL } from "@/features/captions/style";
import type { CaptionStudio } from "@/features/captions/use-caption-studio";

/** Barra superior do estúdio: arquivo, desfazer/refazer e atalho de exportação. */
export function StudioTopBar({ studio }: { studio: CaptionStudio }) {
  const { preset, position, style, sourceLabel, draftStamp, saved, busy } = studio;

  return (
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
        onClick={studio.saveDraft}
        className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-foreground transition hover:bg-muted sm:inline-flex"
      >
        <Save className="size-4" />
        {saved ? "Salvo" : "Arquivo"}
      </button>
      <button
        type="button"
        onClick={studio.discardDraft}
        className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-foreground transition hover:bg-muted md:inline-flex"
      >
        <Trash2 className="size-4" />
        Descartar
      </button>
      <span className="mx-1 hidden h-6 w-px bg-border sm:block" />
      <button
        type="button"
        onClick={studio.undo}
        disabled={!studio.canUndo}
        className="grid size-9 place-items-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:opacity-40"
        aria-label="Desfazer"
      >
        <Undo2 className="size-4" />
      </button>
      <button
        type="button"
        onClick={studio.redo}
        disabled={!studio.canRedo}
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
          onClick={() => studio.setPanel("exportar")}
          disabled={busy}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-60 sm:px-4"
        >
          <span className="sm:hidden">{busy ? "…" : "Exportar"}</span>
          <span className="hidden sm:inline">{busy ? "Renderizando…" : "Exportar legendado"}</span>
        </button>
      </div>
    </header>
  );
}
