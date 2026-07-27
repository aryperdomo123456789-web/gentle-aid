import { CheckCircle2, CircleAlert, Download, Loader2, ShieldCheck, Terminal } from "lucide-react";

import { downloadUrl, type Job, type SterilizationReport } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  idle: "Aguardando",
  queued: "Na fila",
  running: "Processando",
  done: "Concluído",
  error: "Erro",
  cancelled: "Cancelado",
};

export function StatusPanel({
  job,
  error,
  busy,
  emptyHint,
}: {
  job: Job | null;
  error: string | null;
  busy: boolean;
  emptyHint: string;
}) {
  const status = error ? "error" : busy ? "running" : (job?.status ?? "idle");
  const lines = job?.log ?? [];
  const auditSummary = job?.audit_summary ?? job?.sterilization?.audit_summary ?? null;

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Terminal className="size-4 text-primary" aria-hidden="true" />
          Status do processamento
        </h2>
        <StatusPill status={status} />
      </div>

      {error ? (
        <p className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-foreground">
          <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
          {error}
        </p>
      ) : null}

      {job?.message && !error ? (
        <p className="rounded-xl border border-border bg-background/50 p-3 text-sm text-muted-foreground">
          {job.message}
        </p>
      ) : null}

      {auditSummary ? (
        <section className="rounded-xl border border-primary/30 bg-primary/5 p-3">
          <header className="mb-2 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-foreground">Resultado da auditoria</h3>
            <span className="rounded-full border border-border bg-background/70 px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
              entregue no servidor
            </span>
          </header>
          <pre className="whitespace-pre-wrap break-words text-xs leading-5 text-muted-foreground">
            {auditSummary}
          </pre>
        </section>
      ) : null}

      <div className="min-h-40 flex-1 overflow-auto rounded-xl border border-border bg-background/70 p-3">
        {lines.length === 0 ? (
          <p className="font-mono text-xs text-muted-foreground">
            {busy ? "Iniciando FFmpeg…" : emptyHint}
          </p>
        ) : (
          <ol className="space-y-1 font-mono text-xs text-muted-foreground">
            {lines.map((line, i) => (
              <li key={`${i}-${line.slice(0, 12)}`} className="break-words">
                <span className="text-primary">›</span> {line}
              </li>
            ))}
          </ol>
        )}
      </div>

      {job?.sterilization ? <SterilizationBadge report={job.sterilization} /> : null}

      {job?.md5_before || job?.md5_after ? (
        <dl className="grid gap-2 text-xs">
          <HashRow label="MD5 origem" value={job.md5_before} />
          <HashRow label="MD5 esterilizado" value={job.md5_after} />
          <HashRow label="SHA-256 final" value={job.sha256_after} />
        </dl>
      ) : null}

      <a
        href={job?.download_url ? downloadUrl(job.download_url) : undefined}
        download={job?.filename ?? undefined}
        aria-disabled={!job?.download_url}
        className={
          job?.download_url
            ? "inline-flex items-center justify-center gap-2 rounded-xl bg-success px-4 py-3 text-sm font-semibold text-success-foreground transition-opacity hover:opacity-90"
            : "pointer-events-none inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm font-semibold text-muted-foreground"
        }
      >
        <Download className="size-4" aria-hidden="true" />
        {job?.download_url ? "Baixar arquivo final" : "Download indisponível"}
      </a>
    </div>
  );
}

function HashRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/50 px-3 py-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="truncate font-mono text-foreground">{value}</dd>
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    idle: "border-border text-muted-foreground",
    queued: "border-electric/50 bg-electric/10 text-foreground",
    running: "border-electric/50 bg-electric/10 text-foreground",
    done: "border-success/50 bg-success/15 text-foreground",
    error: "border-destructive/50 bg-destructive/15 text-foreground",
    cancelled: "border-border bg-muted/50 text-muted-foreground",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${map[status] ?? map.idle}`}
    >
      {status === "running" || status === "queued" ? (
        <Loader2 className="size-3 animate-spin" aria-hidden="true" />
      ) : status === "done" ? (
        <CheckCircle2 className="size-3 text-success" aria-hidden="true" />
      ) : status === "error" ? (
        <CircleAlert className="size-3 text-destructive" aria-hidden="true" />
      ) : null}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function SterilizationBadge({ report }: { report: SterilizationReport }) {
  return (
    <section className="rounded-xl border border-success/40 bg-success/10 p-3">
      <header className="flex items-center gap-2 text-sm font-semibold">
        <ShieldCheck className="size-4 text-success" aria-hidden="true" />
        {report.unique ? "Arquivo virgem e inrastreável" : "Esterilização aplicada"}
        <span className="ml-auto rounded-full border border-border bg-background/60 px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
          nível {report.level}
        </span>
      </header>
      <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
        {report.steps.map((step) => (
          <li key={step} className="flex gap-2">
            <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-success" aria-hidden="true" />
            <span className="break-words">{step}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] text-muted-foreground">
        {report.video_filters.length} filtro(s) de vídeo · {report.audio_filters.length} de áudio ·
        bitrate {report.bitrate} · {report.attempts} tentativa(s)
      </p>
    </section>
  );
}
