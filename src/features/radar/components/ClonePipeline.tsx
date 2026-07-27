import { Link } from "@tanstack/react-router";
import { Wand2, X } from "lucide-react";

import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import type { Job } from "@/types/job";
import type { RadarVideo } from "../types";

type Props = {
  target: RadarVideo | null;
  cloneLevel: string;
  job: Job | null;
  error: string | null;
  busy: boolean;
  onClose: () => void;
  onCancel: () => void;
  onDelete: () => void;
};

/** Esteira de clonagem: acompanha o job disparado a partir de um card do radar. */
export function ClonePipeline({
  target,
  cloneLevel,
  job,
  error,
  busy,
  onClose,
  onCancel,
  onDelete,
}: Props) {
  if (!target) return null;
  return (
    <section className="panel mt-6 min-w-0 p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Wand2 className="size-4 text-primary" aria-hidden="true" /> Esteira de clonagem
          </h2>
          <p className="mt-1 break-words text-xs text-muted-foreground">
            {target.title} · mutação {cloneLevel}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/historico"
            className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface/60"
          >
            Ver histórico
          </Link>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
          >
            <X className="size-3.5" aria-hidden="true" /> Fechar
          </button>
        </div>
      </div>
      <StatusPanel
        job={job}
        error={error}
        busy={busy}
        emptyHint="Aguardando o download e a esterilização do viral selecionado…"
        onCancel={onCancel}
        onDelete={onDelete}
      />
    </section>
  );
}
