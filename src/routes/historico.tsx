import { createFileRoute } from "@tanstack/react-router";
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { StatusPill } from "@/components/StatusPanel";
import { TopNav } from "@/components/TopNav";
import { apiGet, downloadUrl, friendlyError, type Job } from "@/lib/api";

export const Route = createFileRoute("/historico")({
  head: () => ({
    meta: [
      { title: "Histórico de Jobs — Ecossistema Viral" },
      {
        name: "description",
        content:
          "Repositório central de todos os jobs executados: status, hashes MD5, metadados sanitizados e links de download.",
      },
      { property: "og:title", content: "Histórico de Jobs — Ecossistema Viral" },
      {
        property: "og:description",
        content: "Todos os jobs de FFmpeg executados, com hashes e links de download.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Historico,
});

const TOOL_LABEL: Record<string, string> = {
  youtube: "YouTube Bypass",
  tiktok: "TikTok Clone",
  legendar: "Legendas",
  voice: "Voz V2V",
  canva: "Canva Cleaner",
};

function Historico() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("todos");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ jobs: Job[] }>("/api/jobs");
      setJobs(data.jobs ?? []);
    } catch (err) {
      setError(friendlyError(err));
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = filter === "todos" ? jobs : jobs.filter((j) => j.tool === filter);

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-7xl px-4 py-8 md:px-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold md:text-4xl">Central de Histórico</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Todos os jobs executados no servidor, com status de hash, metadados sanitizados e links de download
              servidos pelo Nginx.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-4 py-2 text-sm font-medium disabled:opacity-60"
          >
            <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            Atualizar
          </button>
        </div>

        <div className="mb-6 flex flex-wrap gap-2">
          {["todos", ...Object.keys(TOOL_LABEL)].map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setFilter(key)}
              className={`rounded-full border px-4 py-1.5 text-xs font-medium transition-colors ${
                filter === key
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border bg-surface/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              {key === "todos" ? "Todos" : TOOL_LABEL[key]}
            </button>
          ))}
        </div>

        {error ? (
          <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">{error}</p>
        ) : null}

        {!error && visible.length === 0 && !loading ? (
          <p className="panel p-8 text-center text-sm text-muted-foreground">
            Nenhum job registrado ainda. Execute uma ferramenta para popular o repositório.
          </p>
        ) : null}

        <div className="space-y-3">
          {visible.map((job) => (
            <article key={job.job_id} className="panel p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-display text-sm font-semibold">
                    {TOOL_LABEL[job.tool] ?? job.tool}
                    <span className="ml-2 font-mono text-xs text-muted-foreground">{job.job_id}</span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {job.filename ?? "—"} · {job.created_at ?? "sem data"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <StatusPill status={job.status} />
                  {job.download_url ? (
                    <a
                      href={downloadUrl(job.download_url)}
                      download={job.filename ?? undefined}
                      className="rounded-full bg-success px-4 py-1.5 text-xs font-semibold text-success-foreground"
                    >
                      Download
                    </a>
                  ) : null}
                </div>
              </div>

              {job.md5_before || job.md5_after ? (
                <dl className="mt-4 grid gap-2 text-xs sm:grid-cols-2">
                  {job.md5_before ? (
                    <div className="rounded-lg border border-border bg-background/50 px-3 py-2">
                      <dt className="text-muted-foreground">MD5 origem</dt>
                      <dd className="truncate font-mono">{job.md5_before}</dd>
                    </div>
                  ) : null}
                  {job.md5_after ? (
                    <div className="rounded-lg border border-border bg-background/50 px-3 py-2">
                      <dt className="text-muted-foreground">MD5 sanitizado</dt>
                      <dd className="truncate font-mono">{job.md5_after}</dd>
                    </div>
                  ) : null}
                </dl>
              ) : null}
            </article>
          ))}
        </div>
      </main>
    </div>
  );
}
