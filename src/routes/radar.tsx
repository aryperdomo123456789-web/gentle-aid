import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Activity,
  Flame,
  Loader2,
  RefreshCw,
  Radar as RadarIcon,
  Sparkles,
  TrendingUp,
  Wand2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Field, SelectInput, TextInput } from "@/components/form";
import { MUTATION_LEVELS } from "@/components/MutationSelect";
import { StatusPanel } from "@/components/StatusPanel";
import { TopNav } from "@/components/TopNav";
import { apiGet, apiPostJson, friendlyError, type Job } from "@/lib/api";
import { useJobRunner } from "@/hooks/use-job-runner";

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
  embed_url?: string | null;
  thumbnail?: string | null;
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
  intelligence: IntelligenceItem[];
  sources: Source[];
};

type IntelligenceItem = {
  topic: string;
  score: number;
  confidence: number;
  horizon: string;
  because: string;
  signals: string[];
  sources: string[];
  formats: string[];
  search_url: string;
  region: string;
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

type RadarSnapshot = {
  nicho: string;
  region: string;
  data: RadarData | null;
  forecast: ForecastData | null;
};

const RADAR_STORAGE_KEY = "radar:last-snapshot";

function readRadarSnapshot(): RadarSnapshot | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(RADAR_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as RadarSnapshot;
    if (!parsed || typeof parsed !== "object") return null;
    return {
      nicho: typeof parsed.nicho === "string" ? parsed.nicho : "",
      region: typeof parsed.region === "string" ? parsed.region : "BR",
      data: parsed.data ?? null,
      forecast: parsed.forecast ?? null,
    };
  } catch {
    return null;
  }
}

function saveRadarSnapshot(snapshot: RadarSnapshot) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(RADAR_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // ignore storage failures
  }
}

function isSnapshot(value: unknown): value is RadarSnapshot {
  if (!value || typeof value !== "object") return false;
  const candidate = value as RadarSnapshot;
  return typeof candidate.nicho === "string" && typeof candidate.region === "string";
}

function RadarGlobal() {
  const [nicho, setNicho] = useState("");
  const [region, setRegion] = useState("BR");
  const [data, setData] = useState<RadarData | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(false);
  const [forecasting, setForecasting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cloneLevel, setCloneLevel] = useState("auto");
  const [cloneTarget, setCloneTarget] = useState<Video | null>(null);
  const [watchTarget, setWatchTarget] = useState<Video | null>(null);
  const cloner = useJobRunner();

  const cloneVideo = useCallback(
    (video: Video) => {
      setCloneTarget(video);
      void cloner.run(() =>
        apiPostJson<Job>("/api/tiktok/clone", { url: video.url, intensity: cloneLevel }),
      );
    },
    [cloneLevel, cloner],
  );

  const load = useCallback(
    async (refresh = false) => {
      setLoading(true);
      setError(null);
      try {
        const qs = new URLSearchParams({ nicho, region, refresh: refresh ? "1" : "0" });
        const next = await apiGet<RadarData>(`/api/radar/global?${qs}`);
        setData(next);
        saveRadarSnapshot({ nicho, region, data: next, forecast });
      } catch (err) {
        setError(friendlyError(err));
      } finally {
        setLoading(false);
      }
    },
    [nicho, region, forecast],
  );

  useEffect(() => {
    const snapshot = readRadarSnapshot();
    if (!snapshot) return;
    setNicho(snapshot.nicho);
    setRegion(snapshot.region);
    setData(snapshot.data);
    setForecast(snapshot.forecast);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (readRadarSnapshot()) return;

    let cancelled = false;
    void (async () => {
      try {
        const qs = new URLSearchParams({ nicho, region });
        const payload = await apiGet<{ snapshot: unknown }>(`/api/radar/snapshot?${qs}`);
        if (cancelled || !isSnapshot(payload.snapshot) || !payload.snapshot.data) return;
        setNicho(payload.snapshot.nicho);
        setRegion(payload.snapshot.region);
        setData(payload.snapshot.data);
        setForecast(payload.snapshot.forecast);
        saveRadarSnapshot(payload.snapshot);
      } catch {
        // silencioso: se não houver snapshot salvo, o botão continua sendo a origem da verdade.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [nicho, region]);

  async function runForecast() {
    setForecasting(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ nicho, region });
      const next = await apiGet<ForecastData>(`/api/radar/forecast?${qs}`);
      setForecast(next);
      saveRadarSnapshot({ nicho, region, data, forecast: next });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setForecasting(false);
    }
  }

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-7xl px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <header className="mb-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-3 py-1 text-xs text-muted-foreground">
            <RadarIcon className="size-3.5 text-primary" aria-hidden="true" /> Radar Global ·
            /api/radar
          </span>
          <h1 className="mt-3 text-2xl font-bold leading-tight sm:text-3xl md:text-4xl">Radar Global de Tendências</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Radar congelado. Só "Varrer radar" atualiza.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="rounded-full border border-border bg-surface/60 px-3 py-1">
              Modo congelado
            </span>
            {data?.generated_at ? (
              <span className="rounded-full border border-border bg-surface/60 px-3 py-1">
                Última coleta: {new Date(data.generated_at).toLocaleString("pt-BR")}
              </span>
            ) : null}
          </div>
        </header>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void load(true);
          }}
          className="panel mb-6 grid gap-4 p-4 sm:p-5 md:grid-cols-[minmax(0,1fr)_180px_auto_auto] md:items-end"
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
            {loading ? "Varredura em andamento…" : "Varrer radar"}
          </button>
          <button
            type="button"
            onClick={() => void runForecast()}
            disabled={forecasting}
            className="mt-auto inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-primary/50 bg-primary/10 px-5 text-sm font-semibold disabled:opacity-60"
          >
            <Sparkles
              className={`size-4 text-primary ${forecasting ? "animate-pulse" : ""}`}
              aria-hidden="true"
            />
            {forecasting ? "Prevendo…" : "Prever nichos"}
          </button>
        </form>

        {error ? (
          <p className="mb-6 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">
            {error}
          </p>
        ) : null}

        {data?.intelligence?.length ? (
          <section className="panel mb-6 min-w-0 p-4 sm:p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                  <Sparkles className="size-4 text-primary" aria-hidden="true" /> Inteligência de
                  Virais
                </h2>
                <p className="text-sm text-muted-foreground">
                  Ranking cruzado entre Google Trends, YouTube, TikTok e pesquisa web.
                </p>
              </div>
              <button
                type="button"
                onClick={() => void load(true)}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-2 text-sm font-medium disabled:opacity-60"
              >
                <RefreshCw
                  className={`size-4 ${loading ? "animate-spin" : ""}`}
                  aria-hidden="true"
                />
                Atualizar inteligência
              </button>
            </div>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
              {data.intelligence.slice(0, 6).map((item) => (
                <article
                  key={item.topic}
                  className="rounded-2xl border border-border bg-background/50 p-4"
                >
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
                          <Flame
                            className="mt-0.5 size-3 shrink-0 text-electric"
                            aria-hidden="true"
                          />
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
              ))}
            </div>
          </section>
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
                {s.name}: {s.ok ? `${s.items} sinais` : "desativado"}
              </span>
            ))}
          </div>
        ) : null}

        {forecast ? (
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
                          <Flame
                            className="mt-0.5 size-3 shrink-0 text-electric"
                            aria-hidden="true"
                          />
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
        ) : null}

        <div className="grid grid-cols-1 gap-4 sm:gap-6 xl:grid-cols-2">
          <section className="panel min-w-0 p-4 sm:p-5">
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
              <TrendingUp className="size-4 text-primary" aria-hidden="true" /> Buscas em alta (
              {data?.region ?? region})
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

          <section className="panel min-w-0 p-4 sm:p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="flex items-center gap-2 text-lg font-semibold">
                <Activity className="size-4 text-electric" aria-hidden="true" /> Vídeos com tração
                real
              </h2>
              <label className="flex w-full items-center gap-2 text-xs text-muted-foreground sm:w-auto">
                Mutação
                <SelectInput
                  aria-label="Nível de esterilização do clone"
                  value={cloneLevel}
                  onChange={(e) => setCloneLevel(e.target.value)}
                  className="h-9 w-full text-xs sm:w-44"
                >
                  {MUTATION_LEVELS.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label}
                    </option>
                  ))}
                </SelectInput>
              </label>
            </div>
            <VideoList
              videos={[
                ...(data?.niche_videos ?? []),
                ...(data?.tiktok ?? []),
                ...(data?.youtube_trending ?? []),
              ]}
              onClone={cloneVideo}
              onWatch={setWatchTarget}
              busy={cloner.busy}
              activeUrl={cloneTarget?.url ?? null}
            />
          </section>
        </div>

        {data?.web?.results?.length ? (
          <section className="panel mt-6 min-w-0 p-4 sm:p-5">
            <h2 className="mb-3 text-lg font-semibold">
              Pesquisa web{data.web.chosen ? ` · melhor fonte: ${data.web.chosen}` : ""}
            </h2>
            <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {data.web.results.map((r) => (
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
        ) : null}
        {cloneTarget ? (
          <section className="panel mt-6 min-w-0 p-4 sm:p-5">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="flex items-center gap-2 text-lg font-semibold">
                  <Wand2 className="size-4 text-primary" aria-hidden="true" /> Esteira de clonagem
                </h2>
                <p className="mt-1 break-words text-xs text-muted-foreground">
                  {cloneTarget.title} · mutação {cloneLevel}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Link
                  to="/historico"
                  className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface/60"
                >
                  Ver histórico
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    cloner.reset();
                    setCloneTarget(null);
                  }}
                  disabled={cloner.busy}
                  className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                >
                  <X className="size-3.5" aria-hidden="true" /> Fechar
                </button>
              </div>
            </div>
            <StatusPanel
              job={cloner.job}
              error={cloner.error}
              busy={cloner.busy}
              emptyHint="Aguardando o download e a esterilização do viral selecionado…"
            />
          </section>
        ) : null}

        {watchTarget ? (
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`Assistir ${watchTarget.title}`}
            className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-background/90 p-2 backdrop-blur-sm sm:p-4"
            onClick={() => setWatchTarget(null)}
          >
            <div
              className="w-full max-w-5xl overflow-hidden rounded-3xl border border-border bg-surface shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-3 border-b border-border px-3 py-3 sm:px-4">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold sm:truncate">{watchTarget.title}</p>
                  <p className="break-words text-xs text-muted-foreground sm:truncate">
                    @{watchTarget.author} · {watchTarget.views_human} visualizações ·{" "}
                    {watchTarget.source}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setWatchTarget(null)}
                  className="rounded-full border border-border px-3 py-1.5 text-xs font-medium hover:bg-background/60"
                >
                  Fechar
                </button>
              </div>
              <div className="bg-black">
                <div className="aspect-video w-full">
                  <iframe
                    src={watchTarget.embed_url ?? watchTarget.url}
                    title={watchTarget.title}
                    className="h-full w-full"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    referrerPolicy="strict-origin-when-cross-origin"
                    allowFullScreen
                  />
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}

function VideoList({
  videos,
  onClone,
  onWatch,
  busy,
  activeUrl,
}: {
  videos: Video[];
  onClone: (video: Video) => void;
  onWatch: (video: Video) => void;
  busy: boolean;
  activeUrl: string | null;
}) {
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
