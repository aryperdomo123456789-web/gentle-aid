import { Loader2, Wand2 } from "lucide-react";

import type { RadarVideo } from "../types";

type Props = {
  videos: RadarVideo[];
  onClone: (video: RadarVideo) => void;
  onWatch: (video: RadarVideo) => void;
  busy: boolean;
  activeUrl: string | null;
};

/** Lista de vídeos com tração real, com ações de assistir e clonar. */
export function VideoList({ videos, onClone, onWatch, busy, activeUrl }: Props) {
  if (!videos.length)
    return <p className="text-sm text-muted-foreground">Rode o radar para listar os virais.</p>;
  return (
    <ul className="space-y-2">
      {videos.slice(0, 20).map((v, i) => {
        const running = busy && activeUrl === v.url;
        return (
          <li
            key={`${v.id}-${i}`}
            className="flex flex-col gap-2 rounded-lg border border-border bg-background/50 px-3 py-2 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-3"
          >
            <div className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => onWatch(v)}
                className="block w-full break-words text-left text-sm font-medium hover:underline"
              >
                {v.title}
              </button>
              <p className="text-xs text-muted-foreground">
                @{v.author} · {v.views_human} visualizações · {v.is_short ? "curto" : "longo"} ·{" "}
                {v.source}
              </p>
            </div>
            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:shrink-0">
              <button
                type="button"
                onClick={() => onWatch(v)}
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold hover:bg-surface/60"
              >
                Assistir
              </button>
              <button
                type="button"
                onClick={() => onClone(v)}
                disabled={busy}
                title="Baixar, esterilizar e entregar o clone virgem"
                className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-primary/50 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-foreground transition hover:bg-primary/20 disabled:opacity-50"
              >
                {running ? (
                  <Loader2 className="size-3.5 animate-spin text-primary" aria-hidden="true" />
                ) : (
                  <Wand2 className="size-3.5 text-primary" aria-hidden="true" />
                )}
                {running ? "Clonando…" : "Clonar"}
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
