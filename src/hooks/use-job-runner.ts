import { useCallback, useRef, useState } from "react";

import { apiGet, friendlyError, type Job } from "@/lib/api";

const POLL_INTERVAL_MS = 1500;
const MAX_RUN_MS = 12 * 60 * 60 * 1000;

/**
 * Executa um job e faz polling em /api/jobs/<id> até done/error/cancelled.
 */
export function useJobRunner() {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAt = useRef<number | null>(null);

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const poll = useCallback((jobId: string) => {
    timer.current = setTimeout(async () => {
      try {
        const next = await apiGet<Job>(`/api/jobs/${jobId}`);
        setJob(next);
        if (next.status === "done" || next.status === "error" || next.status === "cancelled") {
          setBusy(false);
          if (next.status === "error") setError(next.message ?? "O job falhou.");
          startedAt.current = null;
          return;
        }
        if (startedAt.current && Date.now() - startedAt.current > MAX_RUN_MS) {
          setBusy(false);
          setError("Tempo limite excedido aguardando o processamento ao vivo.");
          startedAt.current = null;
          return;
        }
        poll(jobId);
      } catch (err) {
        setBusy(false);
        setError(friendlyError(err));
        startedAt.current = null;
      }
    }, POLL_INTERVAL_MS);
  }, []);

  const run = useCallback(
    async (request: () => Promise<Job>) => {
      stop();
      setBusy(true);
      setError(null);
      setJob(null);
      startedAt.current = Date.now();
      try {
        const started = await request();
        setJob(started);
        if (
          started.status === "done" ||
          started.status === "error" ||
          started.status === "cancelled"
        ) {
          setBusy(false);
          if (started.status === "error") setError(started.message ?? "O job falhou.");
          startedAt.current = null;
          return;
        }
        poll(started.job_id);
      } catch (err) {
        setBusy(false);
        setError(friendlyError(err));
        startedAt.current = null;
      }
    },
    [poll, stop],
  );

  const reset = useCallback(() => {
    stop();
    setJob(null);
    setError(null);
    setBusy(false);
    startedAt.current = null;
  }, [stop]);

  return { job, error, busy, run, reset };
}
