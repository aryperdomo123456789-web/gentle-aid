import type { RadarSource, RadarWebResult } from "../types";

/** Status de cada fonte consultada na varredura. */
export function SourceBadges({ sources }: { sources: RadarSource[] }) {
  if (!sources.length) return null;
  return (
    <div className="mb-6 flex flex-wrap gap-2">
      {sources.map((s) => (
        <span
          key={s.name}
          title={s.error ?? undefined}
          className={`rounded-full border px-3 py-1 text-xs ${
            s.ok
              ? "border-success/50 bg-success/10 text-foreground"
              : "border-border bg-surface/60 text-muted-foreground"
          }`}
        >
          {s.name}: {s.ok ? `${s.items} sinais` : "desativado"}
        </span>
      ))}
    </div>
  );
}

/** Resultados da pesquisa web agregada. */
export function WebResults({
  results,
  chosen,
}: {
  results: RadarWebResult[];
  chosen?: string | null;
}) {
  if (!results.length) return null;
  return (
    <section className="panel mt-6 min-w-0 p-4 sm:p-5">
      <h2 className="mb-3 text-lg font-semibold">
        Pesquisa web{chosen ? ` · melhor fonte: ${chosen}` : ""}
      </h2>
      <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {results.map((r) => (
          <li key={r.url} className="rounded-lg border border-border bg-background/50 p-3">
            <a
              href={r.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-medium hover:underline"
            >
              {r.title}
            </a>
            <p className="mt-1 text-xs text-muted-foreground">{r.snippet}</p>
            <span className="mt-2 inline-block rounded-full border border-border px-2 py-0.5 text-[10px] uppercase text-muted-foreground">
              {r.provider}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
