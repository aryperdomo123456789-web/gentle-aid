import { createFileRoute } from "@tanstack/react-router";
import {
  Activity,
  Flame,
  RefreshCw,
  Radar as RadarIcon,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Field, SelectInput, TextInput } from "@/components/form";
import { TopNav } from "@/components/TopNav";
import { apiGet, friendlyError } from "@/lib/api";

export const Route = createFileRoute("/radar")({
  head: () => ({
    meta: [
      { title: "Radar Global — tendências reais e previsão de nichos" },
      {
        name: "description",
        content:
          "Buscas em alta, vídeos com tração real e previsão de nichos que devem viralizar nos próximos meses.",
      },
      { property: "og:title", content: "Radar Global — Ecossistema Viral" },
      {
        property: "og:description",
        content: "Sinais reais de tendência + previsão de nichos para os próximos 30/60/90 dias.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: RadarGlobal,
});

type Search = { term: string; traffic: string; context?: string; search_url: string };
type Video = {
  id: string;
  title: string;
  author: string;
  views: number;
  views_human: string;
  url: string;
  is_short: boolean;
  source: string;
};
type WebResult = { title: string; url: string; snippet: string; provider: string };
type Source = { name: string; ok: boolean; items?: number; error?: string };

type RadarData = {
  region: string;
  nicho: string;
  generated_at: string;
  searches: Search[];
  youtube_trending: Video[];
  niche_videos: Video[];
  tiktok: Video[];
  web: { results: WebResult[]; chosen?: string | null; providers: Source[] };
  sources: Source[];
};

type ForecastItem = {
  nicho: string;
  horizonte: string;
  confianca: number;
  porque: string;
  angulos?: string[];
  hashtags?: string[];
  formato?: string;
  fonte?: string;
};

type ForecastData = { engine: string; generated_at: string; forecast: ForecastItem[] };

function RadarGlobal() {
  const [nicho, setNicho] = useState("");
  const [region, setRegion] = useState("BR");
  const [data, setData] = useState<RadarData | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(false);
  const [forecasting, setForecasting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (refresh = false) => {
      setLoading(true);
      setError(null);
      try {
        const qs = new URLSearchParams({ nicho, region, refresh: refresh ? "1" : "0" });
        setData(await apiGet<RadarData>(`/api/radar/global?${qs}`));
      } catch (err) {
        setError(friendlyError(err));
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [nicho, region],
  );

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runForecast() {
    setForecasting(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ nicho, region });
      setForecast(await apiGet<ForecastData>(`/api/radar/forecast?${qs}`));
    } catch (err) {
      setError(friendlyError(err));
      setForecast(null);
    } finally {
      setForecasting(false);
    }
  }

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-7xl px-4 py-8 md:px-8">
        <header className="mb-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-3 py-1 text-xs text-muted-foreground">
            <RadarIcon className="size-3.5 text-primary" aria-hidden="true" /> Radar Global · /api/radar
          </span>
          <h1 className="mt-3 text-3xl font-bold md:text-4xl">Radar Global de Tendências</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Sinais reais em tempo real — buscas em alta no Google Trends, vídeos com tração no YouTube e TikTok e
            pesquisa web (Tavily/Exa) — mais a previsão de nichos que devem estourar nos próximos meses.
          </p>
        </header>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void load(true);
          }}
          className="panel mb-6 grid gap-4 p-5 sm:grid-cols-[1fr_180px_auto_auto]"
        >
          <Field label="Nicho (opcional)">
            {(id) => (
              <TextInput
                id={id}
                value={nicho}
                onChange={(e) => setNicho(e.target.value)}
                placeholder="ex.: finanças pessoais, emagrecimento, IA"
                maxLength={60}
              />
            )}
          </Field>
          <Field label="Região">
            {(id) => (
              <SelectInput id={id} value={region} onChange={(e) => setRegion(e.target.value)}>
                <option value="BR">Brasil</option>
                <option value="PT">Portugal</option>
                <option value="US">Estados Unidos</option>
                <option value="MX">México</option>
                <option value="ES">Espanha</option>
              </SelectInput>
            )}
          </Field>
          <button
            type="submit"
            disabled={loading}
            className="mt-auto inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            {loading ? "Varrendo…" : "Varrer radar"}
          </button>
          <button
            type="button"
            onClick={() => void runForecast()}
            disabled={forecasting}
            className="mt-auto inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-primary/50 bg-primary/10 px-5 text-sm font-semibold disabled:opacity-60"
          >
            <Sparkles className={`size-4 text-primary ${forecasting ? "animate-pulse" : ""}`} aria-hidden="true" />
            {forecasting ? "Prevendo…" : "Prever nichos"}
          </button>
        </form>

        {error ? (
          <p className="mb-6 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">{error}</p>
        ) : null}

        {data ? (
          <div className="mb-6 flex flex-wrap gap-2">
            {data.sources.map((s) => (
              <span
                key={s.name}
                title={s.error ?? undefined}
                className={`rounded-full border px-3 py-1 text-xs ${
                  s.ok
                    ? "border-success/50 bg-success/10 text-foreground"
                    : "border-border bg-surface/60 text-muted-foreground"
                }`}
              >
                {s.name}: {s.ok ? `${s.items} sinais` : "off"}
              </span>
            ))}
          </div>
        ) : null}

        {forecast ? (
          <section className="panel mb-8 p-5">
            <header className="mb-4 flex flex-wrap items-center gap-2">
              <Sparkles className="size-4 text-primary" aria-hidden="true" />
              <h2 className="text-lg font-semibold">Previsão de nichos</h2>
              <span className="rounded-full border border-border bg-background/60 px-2 py-0.5 text-[11px] text-muted-foreground">
                motor: {forecast.engine}
              </span>
            </header>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {forecast.forecast.map((f, i) => (
                <article key={`${f.nicho}-${i}`} className="rounded-xl border border-border bg-background/50 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold">{f.nicho}</h3>
                    <span className="shrink-0 rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary">
                      {f.confianca}%
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                    {f.horizonte} · {f.formato ?? "short"}
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
                    <p className="mt-3 font-mono text-[11px] text-muted-foreground">{f.hashtags.join(" ")}</p>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-2">
          <section className="panel p-5">
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
              <TrendingUp className="size-4 text-primary" aria-hidden="true" /> Buscas em alta ({data?.region ?? region})
            </h2>
            {!data?.searches?.length ? (
              <p className="text-sm text-muted-foreground">Sem dados de busca no momento.</p>
            ) : (
              <ol className="space-y-2">
                {data.searches.map((s, i) => (
                  <li
                    key={s.term}
                    className="flex items-start gap-3 rounded-lg border border-border bg-background/50 px-3 py-2"
                  >
                    <span className="font-mono text-xs text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
                    <div className="min-w-0">
                      <a href={s.search_url} target="_blank" rel="noreferrer" className="text-sm font-medium hover:underline">
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

          <section className="panel p-5">
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
              <Activity className="size-4 text-electric" aria-hidden="true" /> Vídeos com tração real
            </h2>
            <VideoList videos={[...(data?.niche_videos ?? []), ...(data?.tiktok ?? []), ...(data?.youtube_trending ?? [])]} />
          </section>
        </div>

        {data?.web?.results?.length ? (
          <section className="panel mt-6 p-5">
            <h2 className="mb-3 text-lg font-semibold">
              Pesquisa web{data.web.chosen ? ` · melhor fonte: ${data.web.chosen}` : ""}
            </h2>
            <ul className="grid gap-3 md:grid-cols-2">
              {data.web.results.map((r) => (
                <li key={r.url} className="rounded-lg border border-border bg-background/50 p-3">
                  <a href={r.url} target="_blank" rel="noreferrer" className="text-sm font-medium hover:underline">
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
        ) : null}
      </main>
    </div>
  );
}

function VideoList({ videos }: { videos: Video[] }) {
  if (!videos.length) return <p className="text-sm text-muted-foreground">Rode o radar para listar virais.</p>;
  return (
    <ul className="space-y-2">
      {videos.slice(0, 20).map((v, i) => (
        <li
          key={`${v.id}-${i}`}
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/50 px-3 py-2"
        >
          <div className="min-w-0 flex-1">
            <a href={v.url} target="_blank" rel="noreferrer" className="block truncate text-sm font-medium hover:underline">
              {v.title}
            </a>
            <p className="text-xs text-muted-foreground">
              @{v.author} · {v.views_human} views · {v.is_short ? "short" : "longo"} · {v.source}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
