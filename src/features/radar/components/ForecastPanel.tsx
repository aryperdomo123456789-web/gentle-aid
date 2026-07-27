import { Sparkles, Flame } from "lucide-react";

import type { ForecastData } from "../types";

/** Previsão de nichos gerada pelo motor de IA. */
export function ForecastPanel({ forecast }: { forecast: ForecastData | null }) {
  if (!forecast) return null;
  return (
    <section className="panel mb-8 min-w-0 p-4 sm:p-5">
      <header className="mb-4 flex flex-wrap items-center gap-2">
        <Sparkles className="size-4 text-primary" aria-hidden="true" />
        <h2 className="text-lg font-semibold">Previsão de nichos</h2>
        <span className="rounded-full border border-border bg-background/60 px-2 py-0.5 text-[11px] text-muted-foreground">
          motor: {forecast.engine}
        </span>
      </header>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {forecast.forecast.map((f, i) => (
          <article
            key={`${f.nicho}-${i}`}
            className="rounded-xl border border-border bg-background/50 p-4"
          >
            <div className="flex items-start justify-between gap-2">
              <h3 className="min-w-0 break-words text-sm font-semibold">{f.nicho}</h3>
              <span className="shrink-0 rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary">
                {f.confianca}%
              </span>
            </div>
            <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
              {f.horizonte} · {f.formato ?? "curto"}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">{f.porque}</p>
            {f.angulos?.length ? (
              <ul className="mt-3 space-y-1 text-xs">
                {f.angulos.map((a) => (
                  <li key={a} className="flex gap-2">
                    <Flame className="mt-0.5 size-3 shrink-0 text-electric" aria-hidden="true" />
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {f.hashtags?.length ? (
              <p className="mt-3 font-mono text-[11px] text-muted-foreground">
                {f.hashtags.join(" ")}
              </p>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
