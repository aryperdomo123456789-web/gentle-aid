import { Music4, Pause, Play, RotateCcw, Type, Video } from "lucide-react";
import { useCallback, useRef } from "react";

import { cn } from "@/lib/utils";

import { formatClock, type PreviewBlock } from "../timeline";

/**
 * Linha do tempo estilo Canva: régua com marcações, faixa de blocos de
 * legenda, faixa do vídeo e faixa de áudio, com playhead arrastável.
 */
export function EditorTimeline({
  duration,
  time,
  playing,
  blocks,
  uppercase,
  sourceLabel,
  poster,
  zoom,
  onZoom,
  onSeek,
  onToggle,
}: {
  duration: number;
  time: number;
  playing: boolean;
  blocks: PreviewBlock[];
  uppercase: boolean;
  sourceLabel: string;
  poster: string | null;
  zoom: number;
  onZoom: (value: number) => void;
  onSeek: (time: number) => void;
  onToggle: () => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const safeDuration = Math.max(1, duration);

  const seekFromPointer = useCallback(
    (clientX: number) => {
      const rect = trackRef.current?.getBoundingClientRect();
      if (!rect) return;
      const pct = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      onSeek(pct * safeDuration);
    },
    [onSeek, safeDuration],
  );

  const step = safeDuration <= 20 ? 5 : safeDuration <= 90 ? 10 : 30;
  const marks: number[] = [];
  for (let t = 0; t <= safeDuration; t += step) marks.push(t);

  return (
    <section
      aria-label="Linha do tempo"
      className="flex flex-col gap-2 border-t border-border bg-card/60 px-3 py-2 sm:px-4"
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggle}
          className="grid size-8 shrink-0 place-items-center rounded-full bg-primary text-primary-foreground transition hover:opacity-90"
          aria-label={playing ? "Pausar" : "Reproduzir"}
        >
          {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
        </button>
        <button
          type="button"
          onClick={() => onSeek(0)}
          className="grid size-8 shrink-0 place-items-center rounded-full border border-border text-muted-foreground transition hover:text-foreground"
          aria-label="Voltar ao início"
        >
          <RotateCcw className="size-4" />
        </button>
        <span className="shrink-0 font-mono text-xs text-muted-foreground">
          {formatClock(time)} / {formatClock(safeDuration)}
        </span>
        <div className="ml-auto flex min-w-0 items-center gap-2">
          <input
            type="range"
            min={1}
            max={3}
            step={0.1}
            value={zoom}
            onChange={(e) => onZoom(Number(e.target.value))}
            className="w-20 accent-primary sm:w-28"
            aria-label="Zoom da linha do tempo"
          />
          <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
            {Math.round(zoom * 100)}%
          </span>
        </div>
      </div>

      <div className="overflow-x-auto pb-1">
        <div style={{ width: `${zoom * 100}%`, minWidth: "100%" }}>
          <div
            ref={trackRef}
            className="relative select-none"
            onPointerDown={(e) => {
              e.preventDefault();
              (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
              seekFromPointer(e.clientX);
            }}
            onPointerMove={(e) => {
              if (e.buttons === 1) seekFromPointer(e.clientX);
            }}
          >
            {/* Régua */}
            <div className="relative h-5 border-b border-border/60">
              {marks.map((mark) => (
                <span
                  key={mark}
                  className="absolute top-0 -translate-x-1/2 font-mono text-[10px] text-muted-foreground"
                  style={{ left: `${(mark / safeDuration) * 100}%` }}
                >
                  {mark}s
                </span>
              ))}
            </div>

            {/* Faixa de legendas */}
            <div className="relative mt-1.5 h-8 rounded-md bg-muted/40">
              {blocks.map((block, index) => {
                const left = (block.start / safeDuration) * 100;
                const width = Math.max(1.2, ((block.end - block.start) / safeDuration) * 100);
                const label = block.words.map((w) => w.text).join(" ");
                const isActive = time >= block.start && time <= block.end;
                return (
                  <button
                    key={`${block.start}-${index}`}
                    type="button"
                    onClick={() => onSeek(block.start + 0.01)}
                    style={{ left: `${left}%`, width: `${width}%` }}
                    className={cn(
                      "absolute top-0 h-8 truncate rounded-md border px-2 text-left text-[11px] leading-8 transition",
                      isActive
                        ? "border-primary bg-primary/30 text-foreground"
                        : "border-primary/30 bg-primary/10 text-muted-foreground hover:bg-primary/20",
                    )}
                    title={label}
                  >
                    {uppercase ? label.toUpperCase() : label}
                  </button>
                );
              })}
              <span className="pointer-events-none absolute left-2 top-0 flex h-8 items-center gap-1 text-[11px] text-muted-foreground/60">
                {blocks.length ? null : (
                  <>
                    <Type className="size-3" /> Sem blocos — cole a transcrição
                  </>
                )}
              </span>
            </div>

            {/* Faixa de vídeo */}
            <div
              className="relative mt-1.5 flex h-10 items-center gap-2 overflow-hidden rounded-md border border-border/60 bg-black/60 px-2"
              style={{
                backgroundImage: poster ? `url(${poster})` : undefined,
                backgroundSize: "auto 100%",
                backgroundRepeat: "repeat-x",
              }}
            >
              <Video className="size-3.5 shrink-0 text-primary" />
              <span className="truncate rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-white">
                {sourceLabel || "Nenhuma mídia selecionada"}
              </span>
            </div>

            {/* Faixa de áudio */}
            <div className="mt-1.5 flex h-7 items-center gap-2 rounded-md border border-dashed border-border/60 px-2 text-[11px] text-muted-foreground">
              <Music4 className="size-3.5 shrink-0" />
              Áudio original preservado — a esterilização mantém a narrativa
            </div>

            {/* Playhead */}
            <div
              className="pointer-events-none absolute inset-y-0 z-10 w-px bg-primary"
              style={{ left: `${Math.min(100, (time / safeDuration) * 100)}%` }}
            >
              <span className="absolute -left-1 top-0 size-2 rotate-45 rounded-[2px] bg-primary" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
