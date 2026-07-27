import { useEffect, useRef } from "react";

import { apiGet } from "../lib/api";

type VersionPayload = {
  status?: string;
  version?: string;
};

export function useAutoReloadOnDeploy() {
  const versionRef = useRef<string | null>(null);

  useEffect(() => {
    let alive = true;
    let inFlight = false;
    const timer = window.setInterval(() => void checkVersion(), 45_000);

    const checkVersion = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const data = await apiGet<VersionPayload>("/api/version");
        if (!alive || !data.version) return;
        if (!versionRef.current) {
          versionRef.current = data.version;
          return;
        }
        if (versionRef.current !== data.version) {
          window.location.reload();
        }
      } catch {
        // Se o backend estiver reiniciando durante um deploy, tentamos de novo no próximo ciclo.
      } finally {
        inFlight = false;
      }
    };

    const onFocus = () => {
      void checkVersion();
    };

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") void checkVersion();
    };

    void checkVersion();
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);
}
