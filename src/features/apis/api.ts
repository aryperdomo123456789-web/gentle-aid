import { apiDelete, apiGet, apiPostJson, apiPutJson } from "@/lib/http";
import type { Provider, ScanReport, TestResult } from "./types";

/** Endpoints do cofre de chaves (`/api/apis`). */

export async function fetchProviders(): Promise<Provider[]> {
  const data = await apiGet<{ providers: Provider[] }>("/api/apis");
  return data.providers ?? [];
}

export async function testAllProviders(): Promise<Provider[]> {
  const data = await apiPostJson<{ providers: Provider[] }>("/api/apis/test-all", {});
  return data.providers ?? [];
}

export type ImportReport = {
  imported: string[];
  skipped: string[];
  scanned: number;
  roots?: string[];
  env_file?: string | null;
};

export function importKeys(options: {
  force: boolean;
  repair?: boolean;
}): Promise<{ providers: Provider[]; report: ImportReport }> {
  return apiPostJson<{ providers: Provider[]; report: ImportReport }>("/api/apis/import", {
    force: options.force,
    repair: options.repair ?? false,
  });
}

export async function scanKeys(): Promise<ScanReport> {
  const data = await apiGet<{ report: ScanReport }>("/api/apis/scan");
  return data.report;
}

export async function saveProviderKey(
  id: string,
  input: { key: string; note: string },
): Promise<Provider> {
  const data = await apiPutJson<{ provider: Provider }>(`/api/apis/${id}`, input);
  return data.provider;
}

export function testProvider(id: string): Promise<{ provider: Provider; result: TestResult }> {
  return apiPostJson<{ provider: Provider; result: TestResult }>(`/api/apis/${id}/test`, {});
}

export async function deleteProviderKey(id: string): Promise<Provider> {
  const data = await apiDelete<{ provider: Provider }>(`/api/apis/${id}`);
  return data.provider;
}
