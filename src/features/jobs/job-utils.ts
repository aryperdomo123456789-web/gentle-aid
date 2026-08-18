import type { Job } from "@/types/job";

/** Rótulos das ferramentas que aparecem nos filtros e cabeçalhos do histórico. */
export const TOOL_LABEL: Record<string, string> = {
  youtube: "Desvio YouTube",
  tiktok: "Clone TikTok",
  legendar: "Legendas",
  transcribe: "Transcrição",
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

/** Rótulos padronizados dos estágios do pipeline (iguais em toda ferramenta). */
export const STAGE_LABEL: Record<string, string> = {
  criado: "Criado",
  processando: "Processando",
  preparando: "Preparando origem",
  baixando: "Baixando mídia",
  transcrevendo: "Transcrevendo",
  narrando: "Narrando",
  mixando: "Mixando",
  esterilizando: "Esterilizando",
  entregue: "Entregue",
  concluido: "Concluído",
  cancelado: "Cancelado",
  falha: "Falha",
  geral: "Geral",
};

export function stageLabel(stage?: string | null): string | null {
  if (!stage) return null;
  return STAGE_LABEL[stage] ?? stage;
}

/** Rótulos das ações registradas na trilha de auditoria. */
export const AUDIT_ACTION_LABEL: Record<string, string> = {
  created: "Job criado",
  queued: "Enfileirado",
  status: "Mudança de status",
  cancel_requested: "Cancelamento solicitado",
  delivered: "Arquivo entregue",
  deleted: "Job excluído",
};

export function auditActionLabel(action: string): string {
  return AUDIT_ACTION_LABEL[action] ?? action;
}

/** 93000 → "1m 33s". */
export function formatDurationMs(ms?: number | null): string {
  if (!ms || ms < 0) return "—";
  const total = Math.round(ms / 1000);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

/** Cor do marcador de cada nível de evento no rastro. */
export function eventTone(level: string): string {
  if (level === "error") return "bg-destructive";
  if (level === "audit" || level === "artifact") return "bg-success";
  if (level === "stage" || level === "lifecycle") return "bg-primary";
  return "bg-muted-foreground";
}
