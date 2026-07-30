import { useCallback, useEffect, useRef, useState } from "react";

import { friendlyError } from "@/lib/http";
import { fetchLibrary, fetchLiveOptions, fetchLiveStatus, startLive, stopLive } from "./api";
import type { LibraryItem, LiveOptions, LivePlatform, LiveSession } from "./types";
import { isLiveActive } from "./types";

/**
 * Estado da estação de live: opções, acervo, status ao vivo e ações.
 *
 * O polling acompanha o supervisor no servidor (que pode estar em outro worker
 * do Gunicorn), então o painel continua correto mesmo após deploy ou restart.
 */
export function useLiveStation(platform: LivePlatform) {
  const [options, setOptions] = useState<LiveOptions | null>(null);
  const [library, setLibrary] = useState<LibraryItem[]>([]);
  const [session, setSession] = useState<LiveSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  const refreshStatus = useCallback(async () => {
    try {
      const next = await fetchLiveStatus(platform);
      if (mounted.current) setSession(next);
    } catch (err) {
      if (mounted.current) setError(friendlyError(err));
    }
  }, [platform]);

  const refreshLibrary = useCallback(async () => {
    try {
      const { items } = await fetchLibrary();
      if (mounted.current) setLibrary(items);
    } catch {
      /* acervo é opcional: upload sempre funciona */
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    setLoading(true);
    void (async () => {
      try {
        const [opts] = await Promise.all([fetchLiveOptions(), refreshLibrary(), refreshStatus()]);
        if (mounted.current) setOptions(opts);
      } catch (err) {
        if (mounted.current) setError(friendlyError(err));
      } finally {
        if (mounted.current) setLoading(false);
      }
    })();
    return () => {
      mounted.current = false;
    };
  }, [refreshLibrary, refreshStatus]);

  // Polling mais rápido quando há transmissão no ar.
  useEffect(() => {
    const active = isLiveActive(session?.status);
    const interval = window.setInterval(() => void refreshStatus(), active ? 4000 : 15000);
    return () => window.clearInterval(interval);
  }, [refreshStatus, session?.status]);

  const start = useCallback(
    async (form: FormData) => {
      setBusy(true);
      setError(null);
      try {
        const next = await startLive(form);
        setSession(next);
        await refreshLibrary();
      } catch (err) {
        setError(friendlyError(err));
      } finally {
        setBusy(false);
        void refreshStatus();
      }
    },
    [refreshLibrary, refreshStatus],
  );

  const stop = useCallback(async () => {
    setBusy(true);
    try {
      const next = await stopLive(platform);
      setSession(next);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
      void refreshStatus();
    }
  }, [platform, refreshStatus]);

  return {
    options,
    library,
    session,
    error,
    busy,
    loading,
    start,
    stop,
    refreshStatus,
    refreshLibrary,
    active: isLiveActive(session?.status),
  };
}
