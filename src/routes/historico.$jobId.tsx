import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, Download, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { StatusPanel } from "@/components/StatusPanel";
import { TopNav } from "@/components/TopNav";
import { API_BASE, apiGet, downloadUrl, friendlyError, type Job } from "@/lib/api";

export const Route = createFileRoute("/historico/$jobId")({
  head: () => ({
    meta: [
      { title: "Detalhe do Job — Jobs Center" },
      {
        name: "description",
        content:
          "Timeline completa do job: etapas de FFmpeg, relatório de esterilização, hashes e download do arquivo final.",
      },
      { property: "og:title", content: "Detalhe do Job — Jobs Center" },
      {
        property: "og:description",
        content: "Timeline, hashes e relatório de esterilização do job.",
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

  async function remove() {
    if (!confirm("Excluir este job e seus arquivos do servidor?")) return;
    try {
      const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Não foi possível excluir o job.");
      void navigate({ to: "/historico" });
    } catch (err) {
      setError(friendlyError(err));
    }
  }

  const meta = Object.entries(job?.meta ?? {});

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-7xl px-4 py-8 md:px-8">
        <Link
          to="/historico"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" aria-hidden="true" /> Voltar ao Jobs Center
        </Link>

        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold md:text-3xl">{job?.tool ?? "Job"}</h1>
            <p className="font-mono text-xs text-muted-foreground">{jobId}</p>
          </div>
          <div className="flex items-center gap-2">
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
              onClick={() => void remove()}
              className="inline-flex items-center gap-2 rounded-full border border-destructive/50 bg-destructive/10 px-4 py-2 text-xs font-semibold"
            >
              <Trash2 className="size-4 text-destructive" aria-hidden="true" /> Excluir
            </button>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
          <section className="panel p-5">
            <h2 className="mb-3 text-lg font-semibold">Dados do job</h2>
            <dl className="grid gap-2 text-xs">
              <Row label="Status" value={job?.status} />
              <Row label="Arquivo" value={job?.filename} />
              <Row label="Criado em" value={job?.created_at} />
              <Row label="Finalizado em" value={job?.finished_at} />
              <Row
                label="Tamanho"
                value={
                  job?.size_bytes ? `${(job.size_bytes / 1024 / 1024).toFixed(2)} MB` : undefined
                }
              />
              {meta.map(([k, v]) => (
                <Row key={k} label={k} value={typeof v === "string" ? v : JSON.stringify(v)} />
              ))}
            </dl>

            {job?.outputs?.length ? (
              <>
                <h3 className="mt-5 text-sm font-semibold">Saídas em lote</h3>
                <ul className="mt-2 space-y-2">
                  {job.outputs.map((o) => (
                    <li
                      key={o.download_url}
                      className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/50 px-3 py-2 text-xs"
                    >
                      <span className="truncate">{o.filename}</span>
                      <a
                        href={downloadUrl(o.download_url)}
                        download={o.filename}
                        className="shrink-0 rounded-full bg-success px-3 py-1 font-semibold text-success-foreground"
                      >
                        Baixar
                      </a>
                    </li>
                  ))}
                </ul>
              </>
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
      </main>
    </div>
  );
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
