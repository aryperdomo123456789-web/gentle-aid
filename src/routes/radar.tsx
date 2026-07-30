import { createFileRoute } from "@tanstack/react-router";
import { RefreshCw, Radar as RadarIcon, Sparkles, Activity } from "lucide-react";

import { Field, SelectInput, TextInput } from "@/components/form";
import { MUTATION_LEVELS } from "@/components/MutationSelect";
import { VIDEO_FORMATS } from "@/components/VideoFormatSelect";
import { TopNav } from "@/components/TopNav";
import { ClonePipeline } from "@/features/radar/components/ClonePipeline";
import { ForecastPanel } from "@/features/radar/components/ForecastPanel";
import { IntelligencePanel } from "@/features/radar/components/IntelligencePanel";
import { SourceBadges, WebResults } from "@/features/radar/components/RadarSignals";
import { TrendingSearches } from "@/features/radar/components/TrendingSearches";
import { VideoList } from "@/features/radar/components/VideoList";
import { WatchDialog } from "@/features/radar/components/WatchDialog";
import { useRadar } from "@/features/radar/use-radar";

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

const REGIONS: { value: string; label: string }[] = [
  { value: "BR", label: "Brasil" },
  { value: "PT", label: "Portugal" },
  { value: "US", label: "Estados Unidos" },
  { value: "MX", label: "México" },
  { value: "ES", label: "Espanha" },
];

function RadarGlobal() {
  const radar = useRadar();
  const { data, cloner } = radar;

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-7xl px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <header className="mb-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-3 py-1 text-xs text-muted-foreground">
            <RadarIcon className="size-3.5 text-primary" aria-hidden="true" /> Radar Global ·
            /api/radar
          </span>
          <h1 className="mt-3 text-2xl font-bold leading-tight sm:text-3xl md:text-4xl">
            Radar Global de Tendências
          </h1>
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
            void radar.load(true);
          }}
          className="panel mb-6 grid gap-4 p-4 sm:p-5 md:grid-cols-[minmax(0,1fr)_180px_auto_auto] md:items-end"
        >
          <Field label="Nicho (opcional)">
            {(id) => (
              <TextInput
                id={id}
                value={radar.nicho}
                onChange={(e) => radar.setNicho(e.target.value)}
                placeholder="ex.: finanças pessoais, emagrecimento, IA"
                maxLength={60}
              />
            )}
          </Field>
          <Field label="Região">
            {(id) => (
              <SelectInput
                id={id}
                value={radar.region}
                onChange={(e) => radar.setRegion(e.target.value)}
              >
                {REGIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </SelectInput>
            )}
          </Field>
          <button
            type="submit"
            disabled={radar.loading}
            className="mt-auto inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            <RefreshCw
              className={`size-4 ${radar.loading ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            {radar.loading ? "Varredura em andamento…" : "Varrer radar"}
          </button>
          <button
            type="button"
            onClick={() => void radar.runForecast()}
            disabled={radar.forecasting}
            className="mt-auto inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-primary/50 bg-primary/10 px-5 text-sm font-semibold disabled:opacity-60"
          >
            <Sparkles
              className={`size-4 text-primary ${radar.forecasting ? "animate-pulse" : ""}`}
              aria-hidden="true"
            />
            {radar.forecasting ? "Prevendo…" : "Prever nichos"}
          </button>
        </form>

        {radar.error ? (
          <p className="mb-6 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">
            {radar.error}
          </p>
        ) : null}

        <IntelligencePanel
          items={data?.intelligence ?? []}
          loading={radar.loading}
          onRefresh={() => void radar.load(true)}
        />

        <SourceBadges sources={data?.sources ?? []} />

        <ForecastPanel forecast={radar.forecast} />

        <div className="grid grid-cols-1 gap-4 sm:gap-6 xl:grid-cols-2">
          <TrendingSearches
            searches={data?.searches ?? []}
            region={data?.region ?? radar.region}
          />

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
                  value={radar.cloneLevel}
                  onChange={(e) => radar.setCloneLevel(e.target.value)}
                  className="h-9 w-full text-xs sm:w-44"
                >
                  {MUTATION_LEVELS.map((l) => (
                    <option key={l.value} value={l.value}>
                      {l.label}
                    </option>
                  ))}
                </SelectInput>
              </label>
              <label className="flex w-full items-center gap-2 text-xs text-muted-foreground sm:w-auto">
                Formato
                <SelectInput
                  aria-label="Formato final do clone"
                  value={radar.cloneFormat}
                  onChange={(e) => radar.setCloneFormat(e.target.value)}
                  className="h-9 w-full text-xs sm:w-44"
                >
                  {VIDEO_FORMATS.map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </SelectInput>
              </label>
            </div>
            <VideoList
              videos={radar.videos}
              onClone={radar.cloneVideo}
              onWatch={radar.setWatchTarget}
              busy={cloner.busy}
              activeUrl={radar.cloneTarget?.url ?? null}
            />
          </section>
        </div>

        <WebResults results={data?.web?.results ?? []} chosen={data?.web?.chosen} />

        <ClonePipeline
          target={radar.cloneTarget}
          cloneLevel={radar.cloneLevel}
          job={cloner.job}
          error={cloner.error}
          busy={cloner.busy}
          onClose={radar.closeClone}
          onCancel={cloner.cancel}
          onDelete={cloner.remove}
        />

        <WatchDialog video={radar.watchTarget} onClose={() => radar.setWatchTarget(null)} />
      </main>
    </div>
  );
}
