import { createFileRoute, Link } from "@tanstack/react-router";
import { RefreshCw, StopCircle, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ConfirmActionDialog } from "@/components/ConfirmActionDialog";
import { StatusPill } from "@/components/StatusPanel";
import { TopNav } from "@/components/TopNav";
import { cancelJob, deleteJob, fetchJobList } from "@/features/jobs/api";
import {
  formatDurationMs,
  isCancellable,
  sourceLabel,
  stageLabel,
  TOOL_LABEL,
  toolLabel,
} from "@/features/jobs/job-utils";
import { formatBytes, formatDateTime } from "@/lib/format";
import { downloadUrl, friendlyError } from "@/lib/api";
import type { Job, JobStats } from "@/types/job";

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

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: "todos", label: "Todos" },
  { key: "running", label: "Em andamento" },
  { key: "done", label: "Concluídos" },
  { key: "error", label: "Com erro" },
  { key: "cancelled", label: "Cancelados" },
];

const EMPTY_STATS: JobStats = {
  total: 0,
  done: 0,
  error: 0,
  cancelled: 0,
  running: 0,
  bytes: 0,
};

function Historico() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("todos");
  const [statusFilter, setStatusFilter] = useState("todos");
  const [search, setSearch] = useState("");
  const [stats, setStats] = useState<JobStats>(EMPTY_STATS);
  const [dialog, setDialog] = useState<{ job: Job; kind: "cancel" | "delete" } | null>(null);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJobList({
        tool: filter === "todos" ? undefined : filter,
        status: statusFilter === "todos" ? undefined : statusFilter,
        q: search.trim() || undefined,
      });
      setJobs(data.jobs);
      setStats(data.stats);
    } catch (err) {
      setError(friendlyError(err));
      setJobs([]);
      setStats(EMPTY_STATS);
    } finally {
      setLoading(false);
    }
  }, [filter, statusFilter, search]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const timer = setInterval(() => {
      void load();
    }, 4000);
    return () => clearInterval(timer);
  }, [load]);

  async function cancel(jobId: string) {
    setBusyJobId(jobId);
    setError(null);
    try {
      await cancelJob(jobId);
      await load();
    } catch (err) {
      setError(friendlyError(err));
      await load();
    } finally {
      setBusyJobId(null);
    }
  }

  async function remove(jobId: string) {
    setBusyJobId(jobId);
    setError(null);
    try {
      await deleteJob(jobId);
      await load();
    } catch (err) {
      setError(friendlyError(err));
      await load();
    } finally {
      setBusyJobId(null);
    }
  }

  const visible = jobs;

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-7xl px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold leading-tight sm:text-3xl md:text-4xl">Central de Histórico</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Todos os jobs executados no servidor, com status de hash, metadados sanitizados e
              links de download servidos pelo Nginx.
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

        <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Jobs listados" value={String(stats.total)} />
          <StatCard label="Em andamento" value={String(stats.running)} />
          <StatCard label="Concluídos" value={String(stats.done)} />
          <StatCard label="Com erro" value={String(stats.error + stats.cancelled)} />
          <StatCard label="Volume entregue" value={formatBytes(stats.bytes)} />
        </div>

        <div className="scroll-x -mx-3 mb-3 flex gap-2 overflow-x-auto px-3 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
          {["todos", ...Object.keys(TOOL_LABEL)].map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setFilter(key)}
              className={`min-h-10 shrink-0 whitespace-nowrap rounded-full border px-4 py-1.5 text-xs font-medium transition-colors ${
                filter === key
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "border-border bg-surface/60 text-muted-foreground hover:text-foreground"
              }`}
            >
              {key === "todos" ? "Todas as ferramentas" : TOOL_LABEL[key]}
            </button>
          ))}
        </div>

        <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="scroll-x -mx-3 flex gap-2 overflow-x-auto px-3 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
            {STATUS_FILTERS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setStatusFilter(item.key)}
                className={`min-h-9 shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  statusFilter === item.key
                    ? "border-primary/60 bg-primary/15 text-foreground"
                    : "border-border bg-surface/60 text-muted-foreground hover:text-foreground"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por id, arquivo ou origem…"
            aria-label="Buscar jobs"
            className="min-h-10 w-full rounded-full border border-border bg-surface/60 px-4 text-xs outline-none focus:border-primary/60 sm:w-72"
          />
        </div>


        {error ? (
          <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">
            {error}
          </p>
        ) : null}

        {!error && visible.length === 0 && !loading ? (
          <p className="panel p-8 text-center text-sm text-muted-foreground">
            Nenhum job registrado ainda. Execute uma ferramenta para popular o repositório.
          </p>
        ) : null}

        <div className="space-y-3">
          {visible.map((job) => (
            <article key={job.job_id} className="panel min-w-0 p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="font-display text-sm font-semibold break-words">
                    {TOOL_LABEL[job.tool] ?? job.tool}
                    <span className="ml-2 break-all font-mono text-xs text-muted-foreground">
                      {job.job_id}
                    </span>
                  </p>
                  <p className="break-words text-xs text-muted-foreground">
                    {job.filename ?? "—"} · {job.created_at ?? "sem data"}
                  </p>
                  {job.source_kind || job.meta?.source_card ? (
                    <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                      {job.source_kind === "upload"
                        ? `Origem: upload${job.source_label ? ` · ${job.source_label}` : ""}`
                        : job.source_kind === "download"
                          ? `Origem: URL${job.source_label ? ` · ${job.source_label}` : ""}`
                          : "Origem: card rastreado"}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:gap-3">
                  <StatusPill status={job.status} />
                  {job.status === "queued" || job.status === "running" ? (
                    <button
                      type="button"
                      onClick={() => setDialog({ job, kind: "cancel" })}
                      disabled={busyJobId === job.job_id}
                      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface/60 px-3 py-1.5 text-xs font-semibold hover:border-primary/50 disabled:opacity-50"
                    >
                      <StopCircle className="size-3.5" aria-hidden="true" />
                      Cancelar
                    </button>
                  ) : null}
                  <Link
                    to="/historico/$jobId"
                    params={{ jobId: job.job_id }}
                    className="rounded-full border border-border bg-surface/60 px-4 py-1.5 text-xs font-semibold hover:border-primary/50"
                  >
                    Detalhes
                  </Link>
                  {job.download_url ? (
                    <a
                      href={downloadUrl(job.download_url)}
                      download={job.filename ?? undefined}
                      className="rounded-full bg-success px-4 py-1.5 text-xs font-semibold text-success-foreground"
                    >
                      Baixar
                    </a>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => setDialog({ job, kind: "delete" })}
                    disabled={busyJobId === job.job_id}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface/60 px-3 py-1.5 text-xs font-semibold hover:border-destructive/50 disabled:opacity-50"
                  >
                    <Trash2 className="size-3.5" aria-hidden="true" />
                    Excluir
                  </button>
                </div>
              </div>

              {job.md5_before || job.md5_after ? (
                <dl className="mt-4 grid gap-2 text-xs sm:grid-cols-2">
                  {job.md5_before ? (
                    <div className="rounded-lg border border-border bg-background/50 px-3 py-2">
                      <dt className="text-muted-foreground">MD5 origem</dt>
                      <dd className="break-all font-mono">{job.md5_before}</dd>
                    </div>
                  ) : null}
                  {job.md5_after ? (
                    <div className="rounded-lg border border-border bg-background/50 px-3 py-2">
                      <dt className="text-muted-foreground">MD5 sanitizado</dt>
                      <dd className="break-all font-mono">{job.md5_after}</dd>
                    </div>
                  ) : null}
                </dl>
              ) : null}
            </article>
          ))}
        </div>
      </main>

      <ConfirmActionDialog
        open={Boolean(dialog)}
        onOpenChange={(open) => {
          if (!open) setDialog(null);
        }}
        title={
          dialog?.kind === "cancel"
            ? `Cancelar job ${dialog.job.job_id}?`
            : `Excluir job ${dialog?.job.job_id ?? ""}?`
        }
        description={
          dialog?.kind === "cancel"
            ? `Tem certeza que quer cancelar ${dialog.job.filename ?? dialog.job.job_id}? O job vai parar e ficar marcado como cancelado.`
            : `Tem certeza que quer apagar ${dialog?.job.filename ?? dialog?.job.job_id}? Isso remove o job, os arquivos gerados e qualquer rastro do servidor.`
        }
        confirmLabel={dialog?.kind === "cancel" ? "Sim, cancelar" : "Sim, apagar"}
        destructive={dialog?.kind === "delete"}
        busy={Boolean(dialog && busyJobId === dialog.job.job_id)}
        onConfirm={async () => {
          if (!dialog) return;
          const current = dialog;
          setDialog(null);
          if (current.kind === "cancel") {
            await cancel(current.job.job_id);
          } else {
            await remove(current.job.job_id);
          }
        }}
      />
    </div>
  );
}
