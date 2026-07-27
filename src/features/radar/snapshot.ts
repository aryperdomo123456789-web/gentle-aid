import { readJson, writeJson } from "@/lib/storage";
import type { RadarSnapshot } from "./types";

const RADAR_STORAGE_KEY = "radar:last-snapshot";

/** Snapshot local — mantém o radar congelado entre recargas de página. */
export function readRadarSnapshot(): RadarSnapshot | null {
  const parsed = readJson<RadarSnapshot>(RADAR_STORAGE_KEY);
  if (!parsed || typeof parsed !== "object") return null;
  return {
    nicho: typeof parsed.nicho === "string" ? parsed.nicho : "",
    region: typeof parsed.region === "string" ? parsed.region : "BR",
    data: parsed.data ?? null,
    forecast: parsed.forecast ?? null,
  };
}

export function saveRadarSnapshot(snapshot: RadarSnapshot): void {
  writeJson(RADAR_STORAGE_KEY, snapshot);
}
