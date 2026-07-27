import { Link } from "@tanstack/react-router";
import { Download, Eye, RefreshCw, StopCircle, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ConfirmActionDialog } from "@/components/ConfirmActionDialog";
import { JobMediaPreview } from "./JobMediaPreview";
import { StatusPill } from "./StatusPanel";
import { cancelJob, deleteJob, fetchJobList } from "@/features/jobs/api";
import {
  formatDurationMs,
  hasPreview,
  isCancellable,
  sourceLabel,
  stageLabel,
} from "@/features/jobs/job-utils";
import { formatBytes, formatDateTime } from "@/lib/format";
import { downloadUrl, friendlyError, type Job } from "@/lib/api";

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
  const [preview, setPreview] = useState<Job | null>(null);
  const [dialog, setDialog] = useState<{ job: Job; kind: "cancel" | "delete" } | null>(null);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJobList({ tool, limit });
      setJobs(data.jobs.slice(0, limit));
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
      if (preview?.job_id === jobId) setPreview(null);
      await load();
    } catch (err) {
      setError(friendlyError(err));
      void load();
    } finally {
      setBusyJobId(null);
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
            className="min-w-0 rounded-xl border border-border bg-background/40 px-3 py-3 sm:px-4"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <p className="break-words text-sm font-medium sm:truncate">{job.filename ?? job.job_id}</p>
                <p className="break-words text-xs text-muted-foreground sm:truncate">
                  {formatDateTime(job.created_at)} · {formatBytes(job.size_bytes)}
                  {job.md5_after ? (
                    <>
                      {" · "}
                      <span className="font-mono">md5 {job.md5_after.slice(0, 10)}</span>
                    </>
                  ) : null}
                  {job.outputs && job.outputs.length > 1 ? ` · ${job.outputs.length} arquivos` : ""}
                  {` · ${formatDurationMs(job.duration_ms)}`}
                </p>
                {stageLabel(job.stage) && !job.terminal ? (
                  <p className="mt-1 text-[11px] uppercase tracking-wide text-primary">
                    Etapa: {stageLabel(job.stage)}
                  </p>
                ) : null}
                {typeof job.meta?.source_card === "object" && job.meta.source_card ? (
                  <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                    {(job.meta.source_card as { title?: string; desc?: string }).title ??
                      "Vídeo de origem"}{" "}
                    - {(job.meta.source_card as { desc?: string }).desc ?? "Sem descrição."}
                  </p>
                ) : null}
                {sourceLabel(job) ? (
                  <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                    Origem rastreada: {sourceLabel(job)}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={job.status} />
                {isCancellable(job) ? (
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
                <button
                  type="button"
                  onClick={() => setPreview(job)}
                  disabled={!hasPreview(job)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface/60 px-3 py-1.5 text-xs font-semibold hover:border-primary/50 disabled:opacity-50"
                >
                  <Eye className="size-3.5" aria-hidden="true" />
                  Assistir
                </button>
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
                  onClick={() => setDialog({ job, kind: "delete" })}
                  aria-label={`Excluir job ${job.job_id}`}
                  disabled={busyJobId === job.job_id}
                  className="rounded-full border border-border bg-surface/60 p-1.5 text-muted-foreground hover:border-destructive/50 hover:text-foreground disabled:opacity-50"
                >
                  <Trash2 className="size-3.5" aria-hidden="true" />
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      {preview ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Prévia do job ${preview.job_id}`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/85 p-4 backdrop-blur-sm"
          onClick={() => setPreview(null)}
        >
          <div className="panel w-full max-w-4xl p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold">{preview.filename ?? preview.job_id}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {preview.tool} · {formatDateTime(preview.created_at)}
                </p>
                {sourceLabel(preview) ? (
                  <p className="truncate text-xs text-muted-foreground">{sourceLabel(preview)}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => setPreview(null)}
                className="rounded-lg border border-border px-3 py-1.5 text-xs font-semibold"
              >
                Fechar
              </button>
            </div>
            <JobMediaPreview job={preview} />
          </div>
        </div>
      ) : null}

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
            ? `Tem certeza que quer cancelar ${dialog.job.filename ?? dialog.job.job_id}? O processamento vai parar e o job ficará marcado como cancelado.`
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
    </section>
  );
}
