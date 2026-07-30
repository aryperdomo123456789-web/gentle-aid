import { Activity, AlertTriangle, CircleDot, Gauge, RefreshCw, Timer } from "lucide-react";

import type { LiveSession } from "../types";

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  idle: { label: "Fora do ar", tone: "text-muted-foreground border-border" },
  starting: { label: "Conectando", tone: "text-warning border-warning/40" },
  live: { label: "NO AR", tone: "text-success border-success/50" },
  reconnecting: { label: "Reconectando", tone: "text-warning border-warning/40" },
  stopping: { label: "Encerrando", tone: "text-warning border-warning/40" },
  stopped: { label: "Encerrada", tone: "text-muted-foreground border-border" },
  error: { label: "Falha", tone: "text-destructive border-destructive/50" },
};

function uptime(seconds?: number): string {
  if (!seconds || seconds < 0) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (d) return `${d}d ${h}h ${m}m`;
  if (h) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-background/40 p-3">
      <p className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
        <Icon className="size-3.5" aria-hidden="true" />
        {label}
      </p>
      <p className="mt-1 truncate font-mono text-sm text-foreground">{value}</p>
    </div>
  );
}

/** Saúde da transmissão: uptime, bitrate, frames, drops e reconexões. */
export function StreamHealth({ session }: { session: LiveSession | null }) {
  const status = session?.status ?? "idle";
  const badge = STATUS_LABEL[status] ?? STATUS_LABEL.idle;
  const metrics = session?.metrics ?? {};

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${badge.tone}`}
        >
          <CircleDot
            className={`size-3.5 ${status === "live" ? "animate-pulse text-success" : ""}`}
            aria-hidden="true"
          />
          {badge.label}
        </span>
        {session?.preset_label ? (
          <span className="rounded-full border border-border px-3 py-1 text-[11px] text-muted-foreground">
            {session.preset_label}
          </span>
        ) : null}
        {session?.rtmp_host ? (
          <span className="rounded-full border border-border px-3 py-1 font-mono text-[11px] text-muted-foreground">
            {session.rtmp_host}
          </span>
        ) : null}
      </div>

      {session?.error ? (
        <p className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {session.error}
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-3">
        <Metric icon={Timer} label="No ar" value={uptime(session?.uptime_seconds)} />
        <Metric icon={Gauge} label="Bitrate" value={metrics.bitrate ?? "—"} />
        <Metric icon={Activity} label="FPS" value={metrics.fps ? String(metrics.fps) : "—"} />
        <Metric
          icon={Activity}
          label="Frames"
          value={metrics.frames ? metrics.frames.toLocaleString("pt-BR") : "—"}
        />
        <Metric
          icon={AlertTriangle}
          label="Descartados"
          value={metrics.dropped !== undefined ? String(metrics.dropped) : "0"}
        />
        <Metric
          icon={RefreshCw}
          label="Reconexões"
          value={session?.reconnects !== undefined ? String(session.reconnects) : "0"}
        />
      </div>

      {session?.sources?.length ? (
        <div className="rounded-xl border border-border bg-background/40 p-3 text-xs">
          <p className="mb-1.5 text-[11px] uppercase tracking-wide text-muted-foreground">
            Playlist em loop
          </p>
          <ol className="space-y-1">
            {session.sources.map((name, index) => (
              <li key={`${name}-${index}`} className="truncate text-muted-foreground">
                <span className="font-mono text-[11px] text-primary">{index + 1}.</span> {name}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
}
