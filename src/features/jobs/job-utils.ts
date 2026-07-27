import type { Job } from "@/types/job";

/** Rótulos das ferramentas que aparecem nos filtros e cabeçalhos do histórico. */
export const TOOL_LABEL: Record<string, string> = {
  youtube: "Desvio YouTube",
  tiktok: "Clone TikTok",
  legendar: "Legendas",
  voice: "Voz V2V",
  canva: "Limpeza Canva",
};

export function toolLabel(tool: string): string {
  return TOOL_LABEL[tool] ?? tool;
}

/** Descreve de onde veio a mídia processada (upload, URL ou card do radar). */
export function sourceLabel(job: Job): string | null {
  if (job.source_kind === "upload") return `Envio local · ${job.source_label ?? "arquivo local"}`;
  if (job.source_kind === "download")
    return `URL · ${job.source_label ?? job.source_url ?? "remota"}`;
  const card = readSourceCard(job);
  if (card?.title) return `Card · ${card.title}`;
  return null;
}

/** Card de descoberta salvo no meta do job, quando existir. */
export function readSourceCard(job: Job | null): Record<string, unknown> | null {
  const raw = job?.meta?.source_card;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  return raw as Record<string, unknown>;
}

/** Há algo assistível: saída pronta ou card de origem rastreado. */
export function hasPreview(job: Job): boolean {
  if (job.download_url || (job.outputs?.length ?? 0) > 0) return true;
  return readSourceCard(job) !== null;
}

/** Job ainda pode ser cancelado. */
export function isCancellable(job: Job): boolean {
  return job.status === "queued" || job.status === "running";
}
