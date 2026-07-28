import { ASPECT_LABEL, type CaptionAspect } from "@/features/captions/style";
import type { CaptionStudio } from "@/features/captions/use-caption-studio";
import { cn } from "@/lib/utils";

const ASPECTS: CaptionAspect[] = ["auto", "9:16", "16:9", "1:1"];

/** Faixa acima do palco: formato do vídeo e escala rápida da legenda. */
export function StageToolbar({ studio }: { studio: CaptionStudio }) {
  const { style, patch, detected } = studio;

  return (
    <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-border/60 bg-card/40 px-3 py-1.5">
      <span className="mr-1 text-[11px] uppercase tracking-wide text-muted-foreground">Formato</span>
      {ASPECTS.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => patch({ aspect: opt })}
          title={ASPECT_LABEL[opt]}
          className={cn(
            "rounded-lg border px-2.5 py-1 text-[11px] transition",
            style.aspect === opt
              ? "border-primary bg-primary/15 text-foreground"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
        >
          {opt === "auto" ? `Auto${detected ? ` · ${detected}` : ""}` : opt}
        </button>
      ))}
      <div className="ml-auto flex items-center gap-2">
        <span className="text-[11px] text-muted-foreground">Legenda</span>
        <input
          type="range"
          min={0.35}
          max={1.8}
          step={0.05}
          value={style.fontScale}
          onChange={(e) => patch({ fontScale: Number(e.target.value) })}
          className="w-24 accent-primary sm:w-36"
          aria-label="Tamanho da legenda"
        />
        <span className="w-10 shrink-0 font-mono text-[11px] text-muted-foreground">
          {style.fontScale.toFixed(2)}x
        </span>
      </div>
    </div>
  );
}
