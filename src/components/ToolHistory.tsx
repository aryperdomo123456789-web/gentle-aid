import { Link } from "@tanstack/react-router";
import { Download, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { StatusPill } from "./StatusPanel";
import { apiDelete, apiGet, downloadUrl, friendlyError, type Job } from "@/lib/api";

function formatBytes(bytes?: number): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function formatDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

/**
 * Histórico local da ferramenta — mesmo padrão do legado:
 * lista dos arquivos prontos, com data, tamanho, hash e download direto.
 */
export function ToolHistory({
  tool,
  title = "Histórico desta ferramenta",
  refreshKey,
  limit = 12,
}: {
  tool: string;
  title?: string;
  refreshKey?: string | number | null;
  limit?: number;
}) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ jobs: Job[] }>(`/api/jobs?tool=${encodeURIComponent(tool)}`);
      setJobs((data.jobs ?? []).slice(0, limit));
    } catch (err) {
      setError(friendlyError(err));
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [tool, limit]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function remove(jobId: string) {
    setJobs((prev) => prev.filter((j) => j.job_id !== jobId));
    try {
      await apiDelete(`/api/jobs/${jobId}`);
    } catch (err) {
      setError(friendlyError(err));
      void load();
    }
  }

  return (
    <section aria-label={title} className="panel p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold">{title}</h2>
          <p className="text-xs text-muted-foreground">
            Arquivos prontos gravados em <code className="font-mono">fabrica_clips/{tool}/</code>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/historico"
            className="rounded-full border border-border bg-surface/60 px-4 py-1.5 text-xs font-medium hover:border-primary/50"
          >
            Central completa
          </Link>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-4 py-1.5 text-xs font-medium disabled:opacity-60"
          >
            <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            Atualizar
          </button>
        </div>
      </div>

      {error ? (
        <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs">
          {error}
        </p>
      ) : null}

      {!error && jobs.length === 0 && !loading ? (
        <p className="rounded-xl border border-border bg-background/40 p-6 text-center text-sm text-muted-foreground">
          Nenhum vídeo processado por esta ferramenta ainda.
        </p>
      ) : null}

      <ul className="space-y-2">
        {jobs.map((job) => (
          <li
            key={job.job_id}
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-background/40 px-4 py-3"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{job.filename ?? job.job_id}</p>
              <p className="truncate text-xs text-muted-foreground">
                {formatDate(job.created_at)} · {formatBytes(job.size_bytes)}
                {job.md5_after ? (
                  <>
                    {" · "}
                    <span className="font-mono">md5 {job.md5_after.slice(0, 10)}</span>
                  </>
                ) : null}
                {job.outputs && job.outputs.length > 1 ? ` · ${job.outputs.length} arquivos` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusPill status={job.status} />
              <Link
                to="/historico/$jobId"
                params={{ jobId: job.job_id }}
                className="rounded-full border border-border bg-surface/60 px-3 py-1.5 text-xs font-semibold hover:border-primary/50"
              >
                Detalhes
              </Link>
              {job.download_url ? (
                <a
                  href={downloadUrl(job.download_url)}
                  download={job.filename ?? undefined}
                  className="inline-flex items-center gap-1.5 rounded-full bg-success px-3 py-1.5 text-xs font-semibold text-success-foreground"
                >
                  <Download className="size-3.5" aria-hidden="true" />
                  Baixar
                </a>
              ) : null}
              <button
                type="button"
                onClick={() => void remove(job.job_id)}
                aria-label={`Excluir job ${job.job_id}`}
                className="rounded-full border border-border bg-surface/60 p-1.5 text-muted-foreground hover:border-destructive/50 hover:text-foreground"
              >
                <Trash2 className="size-3.5" aria-hidden="true" />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
