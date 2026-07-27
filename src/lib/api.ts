/**
 * Barrel público da camada de dados.
 *
 * Mantido para que qualquer módulo continue importando de `@/lib/api`,
 * enquanto a implementação vive em `@/lib/http` e os tipos em `@/types/job`.
 */
export {
  API_BASE,
  ViralApiError,
  apiDelete,
  apiGet,
  apiPostForm,
  apiPostJson,
  apiPutJson,
  buildQuery,
  downloadUrl,
  friendlyError,
} from "@/lib/http";
export type { ApiError } from "@/lib/http";

export { isTerminalStatus } from "@/types/job";
export type {
  Job,
  JobOutput,
  JobStatus,
  SterilizationReport,
  ToolId,
} from "@/types/job";
