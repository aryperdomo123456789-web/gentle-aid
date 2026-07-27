import { useCallback, useRef, useState } from "react";

import { apiGet, friendlyError, type Job } from "@/lib/api";

/**
 * Executa um job e faz polling em /api/jobs/<id> até done/error.
 */
export function useJobRunner() {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const poll = useCallback((jobId: string, attempt = 0) => {
    timer.current = setTimeout(async () => {
      try {
        const next = await apiGet<Job>(`/api/jobs/${jobId}`);
        setJob(next);
        if (next.status === "done" || next.status === "error") {
          setBusy(false);
          if (next.status === "error") setError(next.message ?? "O job falhou.");
          return;
        }
        if (attempt > 600) {
          setBusy(false);
          setError("Tempo limite excedido aguardando o processamento.");
          return;
        }
        poll(jobId, attempt + 1);
      } catch (err) {
        setBusy(false);
        setError(friendlyError(err));
      }
    }, 1500);
  }, []);

  const run = useCallback(
    async (request: () => Promise<Job>) => {
      stop();
      setBusy(true);
      setError(null);
      setJob(null);
      try {
        const started = await request();
        setJob(started);
        if (started.status === "done" || started.status === "error") {
          setBusy(false);
          if (started.status === "error") setError(started.message ?? "O job falhou.");
          return;
        }
        poll(started.job_id);
      } catch (err) {
        setBusy(false);
        setError(friendlyError(err));
      }
    },
    [poll, stop],
  );

  const reset = useCallback(() => {
    stop();
    setJob(null);
    setError(null);
    setBusy(false);
  }, [stop]);

  return { job, error, busy, run, reset };
}
