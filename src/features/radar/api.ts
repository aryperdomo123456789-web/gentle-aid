import { apiGet, apiPostJson, buildQuery } from "@/lib/http";
import type { Job } from "@/types/job";
import type { ForecastData, RadarData, RadarSnapshot } from "./types";

/** Endpoints do Radar Global — única porta de entrada da feature. */

export function fetchRadar(params: { nicho: string; region: string; refresh?: boolean }) {
  return apiGet<RadarData>(
    `/api/radar/global${buildQuery({
      nicho: params.nicho,
      region: params.region,
      refresh: params.refresh ? "1" : "0",
    })}`,
  );
}

export function fetchForecast(params: { nicho: string; region: string }) {
  return apiGet<ForecastData>(`/api/radar/forecast${buildQuery({ ...params })}`);
}

/** Snapshot congelado guardado no servidor (usado quando não há cache local). */
export async function fetchRadarSnapshot(params: {
  nicho: string;
  region: string;
}): Promise<RadarSnapshot | null> {
  const payload = await apiGet<{ snapshot: unknown }>(
    `/api/radar/snapshot${buildQuery({ ...params })}`,
  );
  return isSnapshot(payload.snapshot) ? payload.snapshot : null;
}

/** Clona um viral do radar reaproveitando o pipeline de esterilização do TikTok. */
export function cloneRadarVideo(url: string, intensity: string) {
  return apiPostJson<Job>("/api/tiktok/clone", { url, intensity });
}

export function isSnapshot(value: unknown): value is RadarSnapshot {
  if (!value || typeof value !== "object") return false;
  const candidate = value as RadarSnapshot;
  return typeof candidate.nicho === "string" && typeof candidate.region === "string";
}
