import { History, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { fetchJobTrace } from "@/features/jobs/api";
import { auditActionLabel, eventTone, stageLabel } from "@/features/jobs/job-utils";
import { formatDateTime } from "@/lib/format";
import { friendlyError } from "@/lib/http";
import type { JobTrace as JobTraceData } from "@/types/job";

/**
 * Rastro padronizado de um job: eventos estruturados do pipeline + trilha de
 * auditoria append-only (que sobrevive até à exclusão do job).
 */
export function JobTrace({ jobId, live = false }: { jobId: string; live?: boolean }) {
  const [trace, setTrace] = useState<JobTraceData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setTrace(await fetchJobTrace(jobId));
      setError(null);
    } catch (err) {
      setError(friendlyError(err));
    }
  }, [jobId]);

  useEffect(() => {
    void load();
    if (!live) return;
    const timer = setInterval(() => void load(), 4000);
    return () => clearInterval(timer);
  }, [load, live]);

  const events = trace?.events ?? [];
  const audit = trace?.audit ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="min-w-0">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <History className="size-4 text-primary" aria-hidden="true" />
          Linha do tempo do processamento
        </h3>
        {error ? (
          <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs">
            {error}
          </p>
        ) : null}
        {!error && events.length === 0 ? (
          <p className="rounded-xl border border-border bg-background/50 p-4 text-xs text-muted-foreground">
            Nenhum evento registrado para este job.
          </p>
        ) : null}
        <ol className="max-h-[50vh] space-y-2 overflow-auto pr-1">
          {events.map((event, index) => (
            <li
              key={`${event.ts}-${index}`}
              className="flex min-w-0 gap-3 rounded-xl border border-border bg-background/50 px-3 py-2"
            >
              <span
                className={`mt-1.5 size-2 shrink-0 rounded-full ${eventTone(event.level)}`}
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="break-words text-xs text-foreground">{event.message}</p>
                <p className="mt-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">
                  {formatDateTime(event.ts)} · {stageLabel(event.stage) ?? "geral"} · {event.level}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="min-w-0">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck className="size-4 text-success" aria-hidden="true" />
          Trilha de auditoria (imutável)
        </h3>
        {audit.length === 0 ? (
          <p className="rounded-xl border border-border bg-background/50 p-4 text-xs text-muted-foreground">
            Sem registros de auditoria para este job.
          </p>
        ) : (
          <ol className="max-h-[50vh] space-y-2 overflow-auto pr-1">
            {audit.map((entry, index) => (
              <li
                key={`${entry.ts}-${index}`}
                className="min-w-0 rounded-xl border border-border bg-background/50 px-3 py-2"
              >
                <p className="text-xs font-semibold">{auditActionLabel(entry.action)}</p>
                <p className="break-words text-[11px] text-muted-foreground">
                  {formatDateTime(entry.ts)}
                  {entry.detail ? ` · ${entry.detail}` : ""}
                </p>
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
