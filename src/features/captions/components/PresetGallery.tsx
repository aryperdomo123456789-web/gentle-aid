import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

import type { CaptionPreset } from "../api";

const DEMO_WORDS = ["ISSO", "AQUI", "VAI", "BOMBAR"];

export function PresetCard({
  preset,
  active,
  onSelect,
}: {
  preset: CaptionPreset;
  active: boolean;
  onSelect: () => void;
}) {
  const { preview } = preset;
  const words = preset.uppercase ? DEMO_WORDS : DEMO_WORDS.map((w) => w.toLowerCase());

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className={cn(
        "group relative overflow-hidden rounded-2xl border p-3 text-left transition",
        active
          ? "border-primary ring-2 ring-primary/40"
          : "border-border/60 hover:border-primary/50",
      )}
    >
      {active ? (
        <span className="absolute right-2 top-2 z-10 grid size-6 place-items-center rounded-full bg-primary text-primary-foreground">
          <Check className="size-3.5" />
        </span>
      ) : null}

      <div
        className="flex h-24 items-center justify-center rounded-xl px-3"
        style={{ background: preview.bg }}
      >
        <p
          className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1 text-center leading-tight"
          style={{
            color: preview.color,
            fontWeight: preview.weight,
            fontStyle: preview.italic ? "italic" : "normal",
            fontSize: "0.92rem",
            letterSpacing: preset.uppercase ? "0.02em" : 0,
            textShadow: preview.boxed ? "none" : "0 2px 0 rgba(0,0,0,.85), 0 0 10px rgba(0,0,0,.6)",
          }}
        >
          {words.map((word, index) => {
            const isActive = index === 2;
            return (
              <span
                key={word}
                className={cn(
                  isActive && "caption-demo-active",
                  preview.boxed && "rounded px-1.5 py-0.5",
                )}
                style={{
                  color: isActive ? (preview.boxed ? preview.color : preview.accent) : undefined,
                  background: preview.boxed
                    ? isActive
                      ? preview.accent
                      : "rgba(0,0,0,.72)"
                    : undefined,
                }}
              >
                {word}
              </span>
            );
          })}
        </p>
      </div>

      <div className="mt-2.5 space-y-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold text-foreground">{preset.label}</span>
          <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            {preset.animation}
          </span>
        </div>
        <p className="text-[11px] font-medium text-primary/80">{preset.tag}</p>
        <p className="line-clamp-2 text-xs text-muted-foreground">{preset.description}</p>
      </div>
    </button>
  );
}

export function PresetGallery({
  presets,
  value,
  onChange,
}: {
  presets: CaptionPreset[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {presets.map((preset) => (
        <PresetCard
          key={preset.id}
          preset={preset}
          active={preset.id === value}
          onSelect={() => onChange(preset.id)}
        />
      ))}
    </div>
  );
}
