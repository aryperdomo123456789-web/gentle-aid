import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Download, StopCircle, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ConfirmActionDialog } from "@/components/ConfirmActionDialog";
import { JobMediaPreview } from "@/components/JobMediaPreview";
import { StatusPanel } from "@/components/StatusPanel";
import { TopNav } from "@/components/TopNav";
import { apiDelete, apiGet, apiPostJson, downloadUrl, friendlyError, type Job } from "@/lib/api";

export const Route = createFileRoute("/historico/$jobId")({
  head: () => ({
    meta: [
      { title: "Detalhe do Job — Central de Jobs" },
      {
        name: "description",
        content:
          "Timeline completa do job: vídeo final assistível, ficha da origem, relatório de esterilização, hashes e download.",
      },
      { property: "og:title", content: "Detalhe do Job — Central de Jobs" },
      {
        property: "og:description",
        content: "Prévia do vídeo, metadados da origem e relatório de esterilização do job.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: JobDetail,
});

function JobDetail() {
  const { jobId } = Route.useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<"cancel" | "delete" | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setJob(await apiGet<Job>(`/api/jobs/${jobId}`));
      setError(null);
    } catch (err) {
      setError(friendlyError(err));
    }
  }, [jobId]);

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 4000);
    return () => clearInterval(t);
  }, [load]);

  async function cancel() {
    setBusy(true);
    setError(null);
    try {
      await apiPostJson(`/api/jobs/${jobId}/cancel`, {});
      await load();
    } catch (err) {
      setError(friendlyError(err));
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await apiDelete(`/api/jobs/${jobId}`);
      void navigate({ to: "/historico" });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  const meta = Object.entries(job?.meta ?? {});
  const sourceCard = getSourceCard(job);
  const sourceSummary = getSourceSummary(job);
  const auditSummary = job?.audit_summary ?? job?.sterilization?.audit_summary ?? null;

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-7xl px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <Link
          to="/historico"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" /> Voltar à Central de Jobs
        </Link>

        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold leading-tight sm:text-2xl md:text-3xl">{job?.tool ?? "Job"}</h1>
            <p className="font-mono text-xs text-muted-foreground">{jobId}</p>
          </div>
          <div className="flex items-center gap-2">
            {job?.status === "queued" || job?.status === "running" ? (
              <button
                type="button"
                onClick={() => setDialog("cancel")}
                disabled={busy}
                className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/60 px-4 py-2 text-xs font-semibold disabled:opacity-50"
              >
                <StopCircle className="size-4" aria-hidden="true" /> Cancelar
              </button>
            ) : null}
            {job?.download_url ? (
              <a
                href={downloadUrl(job.download_url)}
                download={job.filename ?? undefined}
                className="inline-flex items-center gap-2 rounded-full bg-success px-4 py-2 text-xs font-semibold text-success-foreground"
              >
                <Download className="size-4" aria-hidden="true" /> Baixar
              </a>
            ) : null}
            <button
              type="button"
              onClick={() => setDialog("delete")}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-full border border-destructive/50 bg-destructive/10 px-4 py-2 text-xs font-semibold"
            >
              <Trash2 className="size-4 text-destructive" aria-hidden="true" /> Excluir
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <section className="panel p-5">
            <h2 className="mb-3 text-lg font-semibold">Prévia do vídeo</h2>
            {job ? <JobMediaPreview job={job} /> : null}

            {sourceCard ? (
              <div className="mt-6 rounded-2xl border border-border bg-background/50 p-4">
                <h3 className="text-sm font-semibold">Informações completas da origem</h3>
                <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                  <Row label="Título" value={sourceCard.title} />
                  <Row label="Descrição" value={sourceCard.desc} />
                  <Row label="Plataforma" value={sourceCard.platform} />
                  <Row label="Autor" value={sourceCard.author ?? sourceCard.nickname} />
                  <Row label="Visualizações" value={sourceCard.views_label} />
                  <Row label="Curtidas" value={sourceCard.likes_label} />
                  <Row label="Comentários" value={sourceCard.comments_label} />
                  <Row label="Compartilhamentos" value={sourceCard.shares_label} />
                  <Row label="Duração" value={sourceCard.duration_label} />
                  <Row label="Data" value={sourceCard.published_label} />
                </div>
              </div>
            ) : null}
          </section>

          <section className="panel p-5">
            <StatusPanel
              job={job}
              error={error}
              busy={job?.status === "running" || job?.status === "queued"}
              emptyHint="Sem logs registrados para este job."
            />
          </section>
        </div>

        {auditSummary ? (
          <section className="panel mt-6 p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Auditoria estrutural entregue</h2>
              <span className="rounded-full border border-border bg-surface/60 px-3 py-1 text-xs font-medium text-muted-foreground">
                relatório persistido
              </span>
            </div>
            <pre className="whitespace-pre-wrap break-words rounded-2xl border border-border bg-background/60 p-4 text-xs leading-5 text-muted-foreground">
              {auditSummary}
            </pre>
          </section>
        ) : null}

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
          <section className="panel p-5">
            <h2 className="mb-3 text-lg font-semibold">Dados do processamento</h2>
            <dl className="grid gap-2 text-xs">
              <Row label="Status" value={job?.status} />
              <Row label="Arquivo" value={job?.filename} />
              <Row label="Origem" value={sourceSummary} />
              <Row label="Caminho origem" value={job?.source_path} />
              <Row label="URL origem" value={job?.source_url} />
              <Row label="Criado em" value={job?.created_at} />
              <Row label="Finalizado em" value={job?.finished_at} />
              <Row
                label="Tamanho"
                value={
                  job?.size_bytes ? `${(job.size_bytes / 1024 / 1024).toFixed(2)} MB` : undefined
                }
              />
              {meta.map(([k, v]) => (
                <Row key={k} label={k} value={formatMetaValue(v)} />
              ))}
            </dl>
          </section>

          <section className="panel p-5">
            <h2 className="mb-3 text-lg font-semibold">Saídas</h2>
            {job?.outputs?.length ? (
              <ul className="space-y-2">
                {job.outputs.map((o) => (
                  <li
                    key={o.download_url}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-background/50 px-3 py-2 text-xs"
                  >
                    <span className="truncate">{o.filename}</span>
                    <div className="flex items-center gap-2">
                      <a
                        href={downloadUrl(o.download_url)}
                        className="rounded-full border border-border px-3 py-1 font-semibold"
                      >
                        Assistir
                      </a>
                      <a
                        href={downloadUrl(o.download_url)}
                        download={o.filename}
                        className="shrink-0 rounded-full bg-success px-3 py-1 font-semibold text-success-foreground"
                      >
                        Baixar
                      </a>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Nenhuma saída registrada.</p>
            )}
          </section>
        </div>
      </main>

      <ConfirmActionDialog
        open={Boolean(dialog)}
        onOpenChange={(open) => {
          if (!open) setDialog(null);
        }}
        title={
          dialog === "cancel"
            ? `Cancelar job ${job?.job_id ?? ""}?`
            : `Excluir job ${job?.job_id ?? ""}?`
        }
        description={
          dialog === "cancel"
            ? `Tem certeza que quer cancelar ${job?.filename ?? job?.job_id}? O processamento vai parar e o job ficará marcado como cancelado.`
            : `Tem certeza que quer apagar ${job?.filename ?? job?.job_id}? Isso remove o job, os arquivos gerados e qualquer rastro do servidor.`
        }
        confirmLabel={dialog === "cancel" ? "Sim, cancelar" : "Sim, apagar"}
        destructive={dialog === "delete"}
        busy={busy}
        onConfirm={async () => {
          const current = dialog;
          setDialog(null);
          if (current === "cancel") {
            await cancel();
          } else {
            await remove();
          }
        }}
      />
    </div>
  );
}

function getSourceCard(job: Job | null) {
  const raw = job?.meta?.source_card;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  return raw as {
    title?: string;
    desc?: string;
    platform?: string;
    author?: string;
    nickname?: string;
    views_label?: string;
    likes_label?: string;
    comments_label?: string;
    shares_label?: string;
    duration_label?: string;
    published_label?: string;
  };
}

function getSourceSummary(job: Job | null) {
  if (!job) return null;
  if (job.source_kind === "upload")
    return `Envio local${job.source_label ? ` · ${job.source_label}` : ""}`;
  if (job.source_kind === "download")
    return `Baixado por URL${job.source_label ? ` · ${job.source_label}` : ""}`;
  const raw = job.meta?.source_card;
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const title = (raw as { title?: string }).title;
    if (title) return `Card de descoberta · ${title}`;
  }
  return null;
}

function formatMetaValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/50 px-3 py-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate font-mono">{value}</dd>
    </div>
  );
}
