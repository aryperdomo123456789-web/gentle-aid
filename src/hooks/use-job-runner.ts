import { useCallback, useEffect, useRef, useState } from "react";

import { cancelJob, deleteJob } from "@/features/jobs/api";
import { apiGet, friendlyError, isTerminalStatus, type Job } from "@/lib/api";
import { readJson, writeJson } from "@/lib/storage";

const POLL_INTERVAL_MS = 1500;
const MAX_RUN_MS = 12 * 60 * 60 * 1000;
const STORAGE_PREFIX = "viral:active-job:";

type Persisted = { jobId: string; startedAt: number };

/**
 * Executa um job, faz polling em /api/jobs/<id> até done/error/cancelled e
 * mantém o job ativo persistido no localStorage — sobrevive a F5/reabertura
 * da aba enquanto o processamento continua no servidor (aaPanel).
 *
 * @param scope chave estável da ferramenta (ex.: "youtube", "voice:dub").
 */
export function useJobRunner(scope?: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startedAt = useRef<number | null>(null);
  const storageKey = scope ? `${STORAGE_PREFIX}${scope}` : null;

  const remember = useCallback(
    (jobId: string | null) => {
      if (!storageKey) return;
      if (typeof window === "undefined") return;
      if (!jobId) {
        try {
          window.localStorage.removeItem(storageKey);
        } catch {
          /* storage bloqueado */
        }
        return;
      }
      writeJson(storageKey, { jobId, startedAt: Date.now() } satisfies Persisted);
    },
    [storageKey],
  );

  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  const poll = useCallback(
    (jobId: string) => {
      timer.current = setTimeout(async () => {
        try {
          const next = await apiGet<Job>(`/api/jobs/${jobId}`);
          setJob(next);
          if (isTerminalStatus(next.status)) {
            setBusy(false);
            if (next.status === "error") setError(next.message ?? "O job falhou.");
            startedAt.current = null;
            remember(null);
            return;
          }
          if (startedAt.current && Date.now() - startedAt.current > MAX_RUN_MS) {
            setBusy(false);
            setError("Tempo limite excedido aguardando o processamento ao vivo.");
            startedAt.current = null;
            remember(null);
            return;
          }
          poll(jobId);
        } catch (err) {
          setBusy(false);
          setError(friendlyError(err));
          startedAt.current = null;
        }
      }, POLL_INTERVAL_MS);
    },
    [remember],
  );

  /** Reanexa ao job ativo depois de um F5. */
  useEffect(() => {
    if (!storageKey) return;
    const saved = readJson<Persisted>(storageKey);
    if (!saved?.jobId) return;
    let cancelled = false;
    void (async () => {
      try {
        const current = await apiGet<Job>(`/api/jobs/${saved.jobId}`);
        if (cancelled) return;
        setJob(current);
        if (isTerminalStatus(current.status)) {
          if (current.status === "error") setError(current.message ?? "O job falhou.");
          remember(null);
          return;
        }
        setBusy(true);
        startedAt.current = saved.startedAt || Date.now();
        poll(current.job_id);
      } catch {
        remember(null);
      }
    })();
    return () => {
      cancelled = true;
      stop();
    };
  }, [poll, remember, stop, storageKey]);

  useEffect(() => stop, [stop]);

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
        if (isTerminalStatus(started.status)) {
          setBusy(false);
          if (started.status === "error") setError(started.message ?? "O job falhou.");
          startedAt.current = null;
          remember(null);
          return;
        }
        remember(started.job_id);
        poll(started.job_id);
      } catch (err) {
        setBusy(false);
        setError(friendlyError(err));
        startedAt.current = null;
        remember(null);
      }
    },
    [poll, remember, stop],
  );

  const refresh = useCallback(async () => {
    if (!job?.job_id) return;
    try {
      setJob(await apiGet<Job>(`/api/jobs/${job.job_id}`));
    } catch {
      /* mantém o último estado conhecido */
    }
  }, [job?.job_id]);

  /** Cancela o job ativo no servidor — o polling segue até o estado final. */
  const cancel = useCallback(async () => {
    if (!job?.job_id) return;
    try {
      await cancelJob(job.job_id);
      await refresh();
    } catch (err) {
      setError(friendlyError(err));
    }
  }, [job?.job_id, refresh]);

  /** Apaga o job e todo o rastro de arquivos no servidor. */
  const remove = useCallback(async () => {
    if (!job?.job_id) return;
    stop();
    try {
      await deleteJob(job.job_id);
    } catch (err) {
      setError(friendlyError(err));
      return;
    }
    remember(null);
    setJob(null);
    setBusy(false);
    setError(null);
    startedAt.current = null;
  }, [job?.job_id, remember, stop]);

  const reset = useCallback(() => {
    stop();
    setJob(null);
    setError(null);
    setBusy(false);
    startedAt.current = null;
    remember(null);
  }, [remember, stop]);

  return { job, error, busy, run, reset, cancel, remove, refresh };
}
