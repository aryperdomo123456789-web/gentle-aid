import { apiDelete, apiGet, apiPostJson, buildQuery } from "@/lib/http";
import type { Job, JobStats, JobTrace } from "@/types/job";

/** Endpoints da Central de Jobs (`/api/jobs`) — única porta de entrada. */

export type JobQuery = {
  tool?: string;
  status?: string;
  q?: string;
  limit?: number;
};

export type JobListResult = {
  jobs: Job[];
  stats: JobStats;
  tools: Record<string, string>;
};

export function fetchJob(jobId: string): Promise<Job> {
  return apiGet<Job>(`/api/jobs/${jobId}`);
}

/** Lista completa com estatísticas — usada pela Central e pelos históricos. */
export async function fetchJobList(query: JobQuery = {}): Promise<JobListResult> {
  const data = await apiGet<Partial<JobListResult>>(`/api/jobs${buildQuery({ ...query })}`);
  return {
    jobs: data.jobs ?? [],
    stats:
      data.stats ??
      ({ total: 0, done: 0, error: 0, cancelled: 0, running: 0, bytes: 0 } satisfies JobStats),
    tools: data.tools ?? {},
  };
}

export async function fetchJobs(tool?: string): Promise<Job[]> {
  const data = await fetchJobList({ tool });
  return data.jobs;
}

/** Rastro completo: eventos estruturados + trilha de auditoria. */
export function fetchJobTrace(jobId: string): Promise<JobTrace> {
  return apiGet<JobTrace>(`/api/jobs/${jobId}/trace`);
}

export function cancelJob(jobId: string): Promise<unknown> {
  return apiPostJson(`/api/jobs/${jobId}/cancel`, {});
}

export function deleteJob(jobId: string): Promise<unknown> {
  return apiDelete(`/api/jobs/${jobId}`);
}
