import { apiDelete, apiGet, apiPostJson } from "@/lib/api";

import type { CreateReleaseKeyInput, ReleaseKey, ReleaseKeysResponse } from "./types";

export async function fetchReleaseKeys(): Promise<ReleaseKey[]> {
  const data = await apiGet<ReleaseKeysResponse>("/api/access-keys");
  return data.keys ?? [];
}

export async function createReleaseKey(input: CreateReleaseKeyInput): Promise<ReleaseKey> {
  const data = await apiPostJson<{ key: ReleaseKey }>("/api/access-keys", input);
  return data.key;
}

export async function revokeReleaseKey(id: string): Promise<ReleaseKey> {
  const data = await apiDelete<{ key: ReleaseKey }>(`/api/access-keys/${id}`);
  return data.key;
}

