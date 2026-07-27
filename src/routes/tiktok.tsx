import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, SelectInput, SubmitButton, TextInput } from "@/components/form";
import { MUTATION_LEVELS } from "@/components/MutationSelect";
import { StatusPanel } from "@/components/StatusPanel";
import { ToolHistory } from "@/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiGet, apiPostJson, friendlyError, type Job } from "@/lib/api";

export const Route = createFileRoute("/tiktok")({
  head: () => ({
    meta: [
      { title: "Painel TikTok — Radar de tendências e clonagem 1:1" },
      {
        name: "description",
        content:
          "Radar de tendências do TikTok, extração de dados de vídeos virais e clonagem 1:1 com esterilização de metadados.",
      },
      { property: "og:title", content: "Painel TikTok — Radar de tendências" },
      {
        property: "og:description",
        content: "Extraia métricas de virais e clone 1:1 com bypass de metadados.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: TikTokDashboard,
});

type Trend = {
  id: string;
  title: string;
  author: string;
  views: number;
  likes: number;
  url: string;
};

function TikTokDashboard() {
  const { job, error, busy, run } = useJobRunner();
  const [nicho, setNicho] = useState("Motivacional");
  const [region, setRegion] = useState("BR");
  const [trends, setTrends] = useState<Trend[]>([]);
  const [radarBusy, setRadarBusy] = useState(false);
  const [radarError, setRadarError] = useState<string | null>(null);
  const [cloneUrl, setCloneUrl] = useState("");
  const [intensity, setIntensity] = useState("auto");

  async function loadRadar(e: React.FormEvent) {
    e.preventDefault();
    setRadarBusy(true);
    setRadarError(null);
    try {
      const data = await apiGet<{ trends: Trend[] }>(
        `/api/tiktok/trends?nicho=${encodeURIComponent(nicho)}&region=${encodeURIComponent(region)}`,
      );
      setTrends(data.trends ?? []);
    } catch (err) {
      setRadarError(friendlyError(err));
      setTrends([]);
    } finally {
      setRadarBusy(false);
    }
  }

  function clone(url: string, sourceCard?: DiscoveryCard) {
    setCloneUrl(url);
    run(() =>
      apiPostJson<Job>("/api/tiktok/clone", {
        url,
        nicho,
        intensity,
        ...(sourceCard ? { source_card: sourceCard } : {}),
      }),
    );
  }

  return (
    <ToolShell
      badge="Ferramenta 2 · /api/tiktok"
      title="Painel TikTok"
      subtitle="Radar de tendências por nicho e região, extração de métricas e clonagem 1:1 de virais com esterilização completa de metadados."
      left={
        <div className="space-y-6">
          <form onSubmit={loadRadar} className="grid gap-5 sm:grid-cols-2">
            <Field label="Nicho">
              {(id) => (
                <TextInput
                  id={id}
                  value={nicho}
                  onChange={(e) => setNicho(e.target.value)}
                  maxLength={60}
                  required
                />
              )}
            </Field>
            <Field label="Região">
              {(id) => (
                <SelectInput id={id} value={region} onChange={(e) => setRegion(e.target.value)}>
                  <option value="BR">Brasil</option>
                  <option value="US">Estados Unidos</option>
                  <option value="PT">Portugal</option>
                  <option value="MX">México</option>
                </SelectInput>
              )}
            </Field>
            <div className="sm:col-span-2">
              <SubmitButton busy={radarBusy} variant="electric">
                {radarBusy ? "Varrendo radar…" : "Atualizar radar de tendências"}
              </SubmitButton>
            </div>
          </form>

          {radarError ? (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm">
              {radarError}
            </p>
          ) : null}

          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-muted-foreground">Virais detectados</h2>
            {trends.length === 0 ? (
              <p className="rounded-xl border border-border bg-background/50 p-4 text-sm text-muted-foreground">
                Nenhum viral carregado ainda. Rode o radar para listar os vídeos em alta do nicho.
              </p>
            ) : (
              <ul className="space-y-3">
                {trends.map((t) => (
                  <li
                    key={t.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-background/50 p-4"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{t.title}</p>
                      <p className="text-xs text-muted-foreground">
                        @{t.author} · {t.views.toLocaleString("pt-BR")} visualizações ·{" "}
                        {t.likes.toLocaleString("pt-BR")} curtidas
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => clone(t.url)}
                      disabled={busy}
                      className="rounded-full bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-60"
                    >
                      Clonar 1:1
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (cloneUrl.trim()) clone(cloneUrl.trim());
            }}
            className="space-y-4 rounded-xl border border-border bg-background/40 p-4"
          >
            <Field label="Clonar por link direto">
              {(id) => (
                <TextInput
                  id={id}
                  type="url"
                  value={cloneUrl}
                  onChange={(e) => setCloneUrl(e.target.value)}
                  placeholder="https://www.tiktok.com/@user/video/123..."
                />
              )}
            </Field>
            <Field
              label="Nível de esterilização"
              hint="Aplicado a qualquer clone, inclusive nos disparados pelo radar acima."
            >
              {(id) => (
                <SelectInput
                  id={id}
                  value={intensity}
                  onChange={(e) => setIntensity(e.target.value)}
                >
                  {MUTATION_LEVELS.map((level) => (
                    <option key={level.value} value={level.value}>
                      {level.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <SubmitButton busy={busy}>{busy ? "Clonando…" : "Clonar viral"}</SubmitButton>
          </form>
        </div>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Escolha um viral do radar ou cole um link para iniciar a clonagem."
        />
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="tiktok"
            actionLabel="Codificar 1:1"
            onAction={(card: DiscoveryCard) => clone(card.url, card)}
            actionBusyUrl={busy ? cloneUrl : null}
          />
          <ToolHistory
            tool="tiktok"
            title="Histórico · Clone TikTok"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
