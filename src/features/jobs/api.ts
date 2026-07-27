import { apiDelete, apiGet, apiPostJson, buildQuery } from "@/lib/http";
import type { Job } from "@/types/job";

/** Endpoints da Central de Jobs (`/api/jobs`). */

export function fetchJob(jobId: string): Promise<Job> {
  return apiGet<Job>(`/api/jobs/${jobId}`);
}

export async function fetchJobs(tool?: string): Promise<Job[]> {
  const data = await apiGet<{ jobs: Job[] }>(`/api/jobs${buildQuery({ tool })}`);
  return data.jobs ?? [];
}

export function cancelJob(jobId: string): Promise<unknown> {
  return apiPostJson(`/api/jobs/${jobId}/cancel`, {});
}

export function deleteJob(jobId: string): Promise<unknown> {
  return apiDelete(`/api/jobs/${jobId}`);
}
