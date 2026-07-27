import { createServerFn } from "@tanstack/react-start";

import { runLabRequest, type LabResult } from "./api-lab.server";

/** Executa uma chamada real do Laboratório de APIs no servidor (sem CORS). */
export const probeApi = createServerFn({ method: "POST" })
  .inputValidator((data: { presetId: string; key: string; values: Record<string, string> }) => {
    if (!data || typeof data.presetId !== "string") throw new Error("presetId obrigatório.");
    return {
      presetId: data.presetId,
      key: typeof data.key === "string" ? data.key.slice(0, 4000) : "",
      values: (data.values ?? {}) as Record<string, string>,
    };
  })
  .handler(async ({ data }): Promise<LabResult> => runLabRequest(data));
