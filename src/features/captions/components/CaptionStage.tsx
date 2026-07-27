import { Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

import type { CaptionPreset } from "../api";
import {
  ASPECT_RATIO,
  detectAspect,
  POSITION_LABEL,
  positionFromY,
  type CaptionAspect,
  type CaptionStyle,
} from "../style";
import {
  blockAt,
  buildWords,
  formatClock,
  groupWords,
  type PreviewBlock,
} from "../timeline";

const ANIM_CLASS: Record<string, string> = {
  pop: "caption-anim-pop",
  bounce: "caption-anim-bounce",
  shake: "caption-anim-shake",
  karaoke: "caption-anim-karaoke",
  typewriter: "caption-anim-fade",
  fade: "caption-anim-fade",
  highlight: "",
  boxed: "",
  none: "",
};

/**
 * Palco de edição estilo Canva: player real do vídeo, legenda sobreposta
 * ao vivo, arraste vertical para posicionar e scrub na timeline. Nada é
 * enviado ao servidor enquanto você testa — o render final no aaPanel usa
 * exatamente os mesmos parâmetros mostrados aqui.
 */
export type CaptionStageApi = { seek: (time: number) => void; toggle: () => void };

export function CaptionStage({
  src,
  poster,
  style,
  preset,
  transcript,
  onYChange,
  onTick,
  onReady,
  onDetectAspect,
  hideControls = false,
  className,
}: {
  src: string | null;
  poster: string | null;
  style: CaptionStyle;
  preset: CaptionPreset | null;
  transcript: string;
  onYChange: (y: number) => void;
  onTick?: (time: number, duration: number, playing: boolean) => void;
  onReady?: (api: CaptionStageApi) => void;
  /** Reporta o formato lido do arquivo real (9:16, 16:9 ou 1:1). */
  onDetectAspect?: (aspect: Exclude<CaptionAspect, "auto">) => void;
  hideControls?: boolean;
  className?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);
  const [duration, setDuration] = useState(12);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [blocks, setBlocks] = useState<PreviewBlock[]>([]);
  const [natural, setNatural] = useState<Exclude<CaptionAspect, "auto"> | null>(null);

  useEffect(() => {
    setBlocks(groupWords(buildWords(transcript, duration), style.wordsPerLine));
  }, [transcript, duration, style.wordsPerLine]);

  // Sem vídeo real, roda um relógio virtual para testar a animação.
  useEffect(() => {
    if (src || !playing) return;
    let last = performance.now();
    const tick = (now: number) => {
      const delta = (now - last) / 1000;
      last = now;
      setTime((t) => (t + delta > duration ? 0 : t + delta));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [src, playing, duration]);

  useEffect(() => {
    setTime(0);
    setPlaying(false);
    setNatural(null);
  }, [src]);

  const toggle = useCallback(() => {
    const video = videoRef.current;
    if (!video) {
      setPlaying((p) => !p);
      return;
    }
    if (video.paused) void video.play();
    else video.pause();
  }, []);

  const seek = useCallback((value: number) => {
    setTime(value);
    if (videoRef.current) videoRef.current.currentTime = value;
  }, []);

  useEffect(() => {
    onReady?.({ seek, toggle });
  }, [onReady, seek, toggle]);

  useEffect(() => {
    onTick?.(time, duration, playing);
  }, [onTick, time, duration, playing]);



  const applyPointer = useCallback(
    (clientY: number) => {
      const rect = stageRef.current?.getBoundingClientRect();
      if (!rect) return;
      const pct = ((clientY - rect.top) / rect.height) * 100;
      onYChange(Math.min(96, Math.max(4, Math.round(pct))));
    },
    [onYChange],
  );

  useEffect(() => {
    if (!dragging) return;
    const move = (e: PointerEvent) => applyPointer(e.clientY);
    const up = () => setDragging(false);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [dragging, applyPointer]);

  const active = blockAt(blocks, time) ?? blocks[0] ?? null;
  const view = preset?.preview;
  const animation = style.animation === "auto" ? preset?.animation ?? "pop" : style.animation;
  const animClass = ANIM_CLASS[animation] ?? "";
  const accent = style.accent || view?.accent || "#ffe500";
  const primary = style.primary || view?.color || "#ffffff";
  const boxed = view?.boxed || animation === "boxed";
  const effectiveAspect: Exclude<CaptionAspect, "auto"> =
    style.aspect === "auto" ? natural ?? "9:16" : style.aspect;

  return (
    <div className={cn("space-y-3", className)}>
      <div
        ref={stageRef}
        className="relative mx-auto h-full max-h-full w-auto max-w-full overflow-hidden rounded-2xl border border-border bg-black shadow-2xl"
        style={{
          aspectRatio: ASPECT_RATIO[effectiveAspect],
          containerType: "inline-size",
          backgroundImage: poster && !src ? `url(${poster})` : undefined,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        {src ? (
          <video
            ref={videoRef}
            src={src}
            playsInline
            className="absolute inset-0 size-full object-contain"
            onLoadedMetadata={(e) => {
              const el = e.currentTarget;
              setDuration(Math.max(1, el.duration || 12));
              const found = detectAspect(el.videoWidth, el.videoHeight);
              setNatural(found);
              onDetectAspect?.(found);
            }}
            onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onEnded={() => setPlaying(false)}
            onClick={toggle}
          />
        ) : (
          <div className="absolute inset-0 grid place-items-center bg-gradient-to-b from-slate-900 to-slate-950 p-6 text-center">
            <p className="text-xs text-muted-foreground">
              {poster
                ? "Prévia do vídeo escolhido na pesquisa — as legendas abaixo simulam o resultado final."
                : "Envie um vídeo para pré-visualizar com a imagem real. Enquanto isso, teste o estilo neste palco."}
            </p>
          </div>
        )}

        {/* Guias de safe area, como no Canva */}
        <div className="pointer-events-none absolute inset-x-0 top-[12%] border-t border-dashed border-white/15" />
        <div className="pointer-events-none absolute inset-x-0 bottom-[12%] border-t border-dashed border-white/15" />

        <div
          role="slider"
          tabIndex={0}
          aria-label="Posição vertical da legenda"
          aria-valuemin={4}
          aria-valuemax={96}
          aria-valuenow={style.yPct}
          onPointerDown={(e) => {
            e.preventDefault();
            setDragging(true);
            applyPointer(e.clientY);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowUp") onYChange(Math.max(4, style.yPct - 2));
            if (e.key === "ArrowDown") onYChange(Math.min(96, style.yPct + 2));
          }}
          className={cn(
            "absolute inset-x-3 -translate-y-1/2 cursor-grab touch-none select-none rounded-lg px-2 py-1 outline-none transition",
            dragging ? "cursor-grabbing ring-2 ring-primary" : "hover:ring-1 hover:ring-primary/50",
          )}
          style={{ top: `${style.yPct}%` }}
        >
          <p
            key={active?.start ?? 0}
            className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-center leading-tight"
            style={{
              color: primary,
              fontWeight: view?.weight ?? 800,
              fontStyle: view?.italic ? "italic" : "normal",
              fontSize: `clamp(0.62rem, ${(7 * style.fontScale).toFixed(2)}cqw, ${(2.3 * style.fontScale).toFixed(2)}rem)`,
              textShadow: boxed ? "none" : "0 2px 0 rgba(0,0,0,.9), 0 0 14px rgba(0,0,0,.65)",
            }}
          >
            {(active?.words ?? []).map((word, i) => {
              const isActive = time >= word.start && time <= word.end;
              const label = style.uppercase ? word.text.toUpperCase() : word.text;
              return (
                <span
                  key={`${word.text}-${i}`}
                  className={cn(isActive && animClass, boxed && "rounded px-1.5 py-0.5")}
                  style={{
                    color: isActive && !boxed ? accent : primary,
                    background: boxed
                      ? isActive
                        ? accent
                        : "rgba(0,0,0,.72)"
                      : undefined,
                  }}
                >
                  {label}
                </span>
              );
            })}
          </p>
        </div>

        <span className="absolute left-3 top-3 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-white">
          {effectiveAspect} · {POSITION_LABEL[positionFromY(style.yPct)]} · {style.yPct}%
          {style.aspect === "auto" ? " · auto" : ""}
        </span>
      </div>

      {hideControls ? null : (
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={toggle}
          className="grid size-9 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground transition hover:opacity-90"
          aria-label={playing ? "Pausar prévia" : "Reproduzir prévia"}
        >
          {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
        </button>
        <button
          type="button"
          onClick={() => seek(0)}
          className="grid size-9 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition hover:text-foreground"
          aria-label="Voltar ao início"
        >
          <RotateCcw className="size-4" />
        </button>
        <input
          type="range"
          min={0}
          max={duration}
          step={0.05}
          value={Math.min(time, duration)}
          onChange={(e) => seek(Number(e.target.value))}
          className="w-full accent-primary"
          aria-label="Linha do tempo"
        />
        <span className="shrink-0 font-mono text-xs text-muted-foreground">
          {formatClock(time)} / {formatClock(duration)}
        </span>
      </div>
      )}
    </div>
  );
}
