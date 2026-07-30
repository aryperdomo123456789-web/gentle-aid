import { Film, RefreshCw, Trash2 } from "lucide-react";

import { formatBytes } from "@/lib/format";
import type { LibraryItem } from "../types";

const TOOL_LABEL: Record<string, string> = {
  youtube: "Desvio YouTube",
  tiktok: "Clone TikTok",
  legendar: "Legendas",
  canva: "Limpeza Canva",
  studio: "Estúdio IA",
  recap: "Recap Narrado",
  voice: "Voz",
  live: "Enviado para live",
};

/** Escolha da playlist: acervo das outras ferramentas + ordem de reprodução. */
export function PlaylistPicker({
  library,
  selected,
  onToggle,
  onClear,
  onRefresh,
  disabled,
}: {
  library: LibraryItem[];
  selected: string[];
  onToggle: (path: string) => void;
  onClear: () => void;
  onRefresh: () => void;
  disabled?: boolean;
}) {
  const byPath = new Map(library.map((item) => [item.path, item]));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[13px] font-semibold tracking-tight text-foreground">
          Playlist do acervo
        </p>
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border px-2.5 text-[11px] text-muted-foreground transition hover:text-foreground"
          >
            <RefreshCw className="size-3.5" aria-hidden="true" />
            Atualizar
          </button>
          {selected.length ? (
            <button
              type="button"
              onClick={onClear}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border px-2.5 text-[11px] text-muted-foreground transition hover:text-destructive"
            >
              <Trash2 className="size-3.5" aria-hidden="true" />
              Limpar
            </button>
          ) : null}
        </div>
      </div>

      {selected.length ? (
        <ol className="space-y-1.5 rounded-xl border border-primary/40 bg-primary/5 p-3 text-xs">
          {selected.map((path, index) => (
            <li key={path} className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-primary">{index + 1}.</span>
              <span className="min-w-0 flex-1 truncate text-foreground">
                {byPath.get(path)?.name ?? path}
              </span>
              <button
                type="button"
                onClick={() => onToggle(path)}
                className="shrink-0 rounded px-1.5 text-[11px] text-muted-foreground transition hover:text-destructive"
              >
                remover
              </button>
            </li>
          ))}
        </ol>
      ) : null}

      <div className="max-h-64 space-y-1 overflow-y-auto rounded-xl border border-border bg-background/40 p-2">
        {library.length === 0 ? (
          <p className="p-3 text-xs text-muted-foreground">
            Nenhum vídeo pronto no acervo ainda — envie um arquivo abaixo.
          </p>
        ) : (
          library.map((item) => {
            const active = selected.includes(item.path);
            return (
              <button
                key={item.path}
                type="button"
                disabled={disabled}
                onClick={() => onToggle(item.path)}
                className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition ${
                  active
                    ? "bg-primary/15 text-foreground"
                    : "text-muted-foreground hover:bg-surface/70 hover:text-foreground"
                }`}
              >
                <Film className="size-3.5 shrink-0" aria-hidden="true" />
                <span className="min-w-0 flex-1 truncate">{item.name}</span>
                <span className="shrink-0 text-[10px] uppercase tracking-wide">
                  {TOOL_LABEL[item.tool] ?? item.tool}
                </span>
                <span className="shrink-0 font-mono text-[10px]">{formatBytes(item.size_bytes)}</span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
