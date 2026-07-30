import { useCallback, useEffect, useState } from "react";

import { useJobRunner } from "@/hooks/use-job-runner";
import { friendlyError } from "@/lib/api";
import { cloneRadarVideo, fetchForecast, fetchRadar, fetchRadarSnapshot } from "./api";
import { readRadarSnapshot, saveRadarSnapshot } from "./snapshot";
import type { ForecastData, RadarData, RadarVideo } from "./types";

/**
 * Estado do Radar Global: consulta, previsão, snapshot congelado e clonagem.
 * Mantém a UI declarativa — a página só renderiza o que este hook expõe.
 */
export function useRadar() {
  const [nicho, setNicho] = useState("");
  const [region, setRegion] = useState("BR");
  const [data, setData] = useState<RadarData | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [loading, setLoading] = useState(false);
  const [forecasting, setForecasting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cloneLevel, setCloneLevel] = useState("auto");
  const [cloneFormat, setCloneFormat] = useState("original");
  const [cloneTarget, setCloneTarget] = useState<RadarVideo | null>(null);
  const [watchTarget, setWatchTarget] = useState<RadarVideo | null>(null);
  const cloner = useJobRunner("radar");

  const load = useCallback(
    async (refresh = false) => {
      setLoading(true);
      setError(null);
      try {
        const next = await fetchRadar({ nicho, region, refresh });
        setData(next);
        saveRadarSnapshot({ nicho, region, data: next, forecast });
      } catch (err) {
        setError(friendlyError(err));
      } finally {
        setLoading(false);
      }
    },
    [nicho, region, forecast],
  );

  const runForecast = useCallback(async () => {
    setForecasting(true);
    setError(null);
    try {
      const next = await fetchForecast({ nicho, region });
      setForecast(next);
      saveRadarSnapshot({ nicho, region, data, forecast: next });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setForecasting(false);
    }
  }, [nicho, region, data]);

  const cloneVideo = useCallback(
    (video: RadarVideo) => {
      setCloneTarget(video);
      // Leva o card do radar junto: título, autor, views, thumb e player.
      void cloner.run(() =>
        cloneRadarVideo(video.url, cloneLevel, {
          title: video.title,
          desc: video.title,
          author: video.author,
          platform: video.source,
          url: video.url,
          embed_url: video.embed_url ?? null,
          thumbnail: video.thumbnail ?? null,
          views_label: video.views_human,
        },
        { video_format: cloneFormat, format_fit: "cover" }),
      );
    },
    [cloneFormat, cloneLevel, cloner],
  );


  const closeClone = useCallback(() => {
    cloner.reset();
    setCloneTarget(null);
  }, [cloner]);

  // Cache local primeiro: o radar é congelado e só "Varrer radar" atualiza.
  useEffect(() => {
    const snapshot = readRadarSnapshot();
    if (!snapshot) return;
    setNicho(snapshot.nicho);
    setRegion(snapshot.region);
    setData(snapshot.data);
    setForecast(snapshot.forecast);
  }, []);

  // Sem cache local: tenta recuperar o último snapshot salvo no servidor.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (readRadarSnapshot()) return;

    let cancelled = false;
    void (async () => {
      try {
        const snapshot = await fetchRadarSnapshot({ nicho, region });
        if (cancelled || !snapshot?.data) return;
        setNicho(snapshot.nicho);
        setRegion(snapshot.region);
        setData(snapshot.data);
        setForecast(snapshot.forecast);
        saveRadarSnapshot(snapshot);
      } catch {
        // silencioso: sem snapshot salvo, o botão continua sendo a origem da verdade.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [nicho, region]);

  const videos: RadarVideo[] = [
    ...(data?.niche_videos ?? []),
    ...(data?.tiktok ?? []),
    ...(data?.youtube_trending ?? []),
  ];

  return {
    nicho,
    setNicho,
    region,
    setRegion,
    data,
    forecast,
    loading,
    forecasting,
    error,
    cloneLevel,
    cloneFormat,
    setCloneFormat,
    setCloneLevel,
    cloneTarget,
    watchTarget,
    setWatchTarget,
    videos,
    cloner,
    load,
    runForecast,
    cloneVideo,
    closeClone,
  };
}
