import { Flame, Sparkles } from "lucide-react";

import type { IntelligenceItem } from "../types";

type Props = {
  items: IntelligenceItem[];
  loading: boolean;
  onRefresh: () => void;
};

/** Ranking cruzado entre Google Trends, YouTube, TikTok e pesquisa web. */
export function IntelligencePanel({ items, loading, onRefresh }: Props) {
  if (!items.length) return null;
  return (
    <section className="panel mb-6 min-w-0 p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Sparkles className="size-4 text-primary" aria-hidden="true" /> Inteligência de Virais
          </h2>
          <p className="text-sm text-muted-foreground">
            Ranking cruzado entre Google Trends, YouTube, TikTok e pesquisa web.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-2 text-sm font-medium disabled:opacity-60"
        >
          <RefreshIcon spinning={loading} />
          Atualizar inteligência
        </button>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
        {items.slice(0, 6).map((item) => (
          <IntelligenceCard key={item.topic} item={item} />
        ))}
      </div>
    </section>
  );
}

function IntelligenceCard({ item }: { item: IntelligenceItem }) {
  return (
    <article className="rounded-2xl border border-border bg-background/50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="break-words text-sm font-semibold">{item.topic}</h3>
          <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            {item.horizon} · {item.sources.length} fonte(s)
          </p>
        </div>
        <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-semibold text-primary">
          {item.score}
        </span>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{item.because}</p>
      {item.signals?.length ? (
        <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
          {item.signals.map((signal) => (
            <li key={signal} className="flex gap-2">
              <Flame className="mt-0.5 size-3 shrink-0 text-electric" aria-hidden="true" />
              <span>{signal}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {item.formats.slice(0, 2).map((format) => (
          <span
            key={format}
            className="rounded-full border border-border bg-surface/60 px-2 py-0.5 text-[11px] text-muted-foreground"
          >
            {format}
          </span>
        ))}
      </div>
      <a
        href={item.search_url}
        target="_blank"
        rel="noreferrer"
        className="mt-3 inline-flex text-xs font-medium text-primary hover:underline"
      >
        Pesquisar este tema
      </a>
    </article>
  );
}

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      className={`size-4 ${spinning ? "animate-spin" : ""}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12a9 9 0 1 1-3-6.7L21 8" />
      <path d="M21 3v5h-5" />
    </svg>
  );
}
