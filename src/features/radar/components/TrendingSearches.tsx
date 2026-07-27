import { TrendingUp } from "lucide-react";

import type { RadarSearch } from "../types";

/** Buscas em alta do Google Trends para a região consultada. */
export function TrendingSearches({ searches, region }: { searches: RadarSearch[]; region: string }) {
  return (
    <section className="panel min-w-0 p-4 sm:p-5">
      <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
        <TrendingUp className="size-4 text-primary" aria-hidden="true" /> Buscas em alta ({region})
      </h2>
      {!searches.length ? (
        <p className="text-sm text-muted-foreground">Sem dados de busca no momento.</p>
      ) : (
        <ol className="space-y-2">
          {searches.map((s, i) => (
            <li
              key={s.term}
              className="flex items-start gap-3 rounded-lg border border-border bg-background/50 px-3 py-2"
            >
              <span className="font-mono text-xs text-muted-foreground">
                {String(i + 1).padStart(2, "0")}
              </span>
              <div className="min-w-0">
                <a
                  href={s.search_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm font-medium hover:underline"
                >
                  {s.term}
                </a>
                <p className="text-xs text-muted-foreground">
                  {s.traffic} {s.context ? `· ${s.context}` : ""}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
