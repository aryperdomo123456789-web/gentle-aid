import { apiGet, apiPostForm, apiPostJson, buildQuery } from "@/lib/http";
import type { LibraryItem, LiveOptions, LivePlatform, LiveSession } from "./types";

/** Endpoints da Estação de Live 24/7 — única porta de entrada da feature. */

export function fetchLiveOptions() {
  return apiGet<LiveOptions>("/api/live/options");
}

export function fetchLibrary() {
  return apiGet<{ items: LibraryItem[] }>("/api/live/library");
}

export function fetchLiveStatus(platform: LivePlatform, signal?: AbortSignal) {
  return apiGet<LiveSession>(`/api/live/status${buildQuery({ platform })}`, signal);
}

export function startLive(form: FormData) {
  return apiPostForm<LiveSession>("/api/live/start", form);
}

export function stopLive(platform: LivePlatform) {
  return apiPostJson<LiveSession>("/api/live/stop", { platform });
}
