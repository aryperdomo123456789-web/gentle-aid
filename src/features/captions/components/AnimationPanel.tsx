import { Field, SelectInput } from "@/components/form";
import {
  ANIMATION_LABELS,
  type CaptionAnimation,
} from "@/features/captions/api";
import {
  ASPECT_LABEL,
  POSITION_LABEL,
  yFromPosition,
  type CaptionAspect,
} from "@/features/captions/style";
import type { CaptionStudio } from "@/features/captions/use-caption-studio";
import { cn } from "@/lib/utils";

const FONT_PRESETS = [
  { label: "Pequena", value: 0.6 },
  { label: "Média", value: 1 },
  { label: "Grande", value: 1.4 },
];

/** Painel "Animação": movimento, ritmo, posição e escala da legenda. */
export function AnimationPanel({ studio }: { studio: CaptionStudio }) {
  const { style, patch, position, detected } = studio;

  return (
    <div className="space-y-4">
      <Field label="Animação">
        {(id) => (
          <SelectInput
            id={id}
            value={style.animation}
            onChange={(e) => patch({ animation: e.target.value as CaptionAnimation })}
          >
            {(Object.keys(ANIMATION_LABELS) as CaptionAnimation[]).map((key) => (
              <option key={key} value={key}>
                {ANIMATION_LABELS[key]}
              </option>
            ))}
          </SelectInput>
        )}
      </Field>

      <label className="flex items-start gap-2 rounded-xl border border-border/60 bg-muted/20 p-3 text-sm text-foreground">
        <input
          type="checkbox"
          checked={style.beatSync}
          onChange={(e) => patch({ beatSync: e.target.checked })}
          className="mt-0.5 size-4 accent-primary"
        />
        <span>
          Legenda no ritmo da música
          <span className="mt-0.5 block text-xs text-muted-foreground">
            O servidor analisa a trilha do vídeo, detecta o BPM e encaixa cada palavra na batida.
            Combina com a animação “Beat”.
          </span>
        </span>
      </label>

      <Field label="Posição" hint={`Arraste no palco para ajuste fino · atual ${style.yPct}%`}>
        {(id) => (
          <SelectInput
            id={id}
            value={position}
            onChange={(e) =>
              patch({ yPct: yFromPosition(e.target.value as "top" | "center" | "bottom") })
            }
          >
            {(["top", "center", "bottom"] as const).map((p) => (
              <option key={p} value={p}>
                {POSITION_LABEL[p]}
              </option>
            ))}
          </SelectInput>
        )}
      </Field>

      <Field
        label={`Palavras por bloco · ${style.wordsPerLine}`}
        hint="1–3 palavras = retenção máxima."
      >
        {(id) => (
          <input
            id={id}
            type="range"
            min={1}
            max={10}
            step={1}
            value={style.wordsPerLine}
            onChange={(e) => patch({ wordsPerLine: Number(e.target.value) })}
            className="w-full accent-primary"
          />
        )}
      </Field>

      <Field
        label={`Tamanho da fonte · ${style.fontScale.toFixed(2)}x`}
        hint="Arraste para a esquerda para deixar a legenda menor e mais discreta."
      >
        {(id) => (
          <input
            id={id}
            type="range"
            min={0.35}
            max={1.8}
            step={0.05}
            value={style.fontScale}
            onChange={(e) => patch({ fontScale: Number(e.target.value) })}
            className="w-full accent-primary"
          />
        )}
      </Field>

      <div className="flex flex-wrap gap-2">
        {FONT_PRESETS.map((opt) => (
          <button
            key={opt.label}
            type="button"
            onClick={() => patch({ fontScale: opt.value })}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-xs transition",
              Math.abs(style.fontScale - opt.value) < 0.03
                ? "border-primary bg-primary/15 text-foreground"
                : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <Field
        label="Formato do vídeo"
        hint={
          style.aspect === "auto"
            ? `Detectado automaticamente: ${detected ?? "aguardando o vídeo"}`
            : "Formato fixado manualmente para a prévia."
        }
      >
        {(id) => (
          <SelectInput
            id={id}
            value={style.aspect}
            onChange={(e) => patch({ aspect: e.target.value as CaptionAspect })}
          >
            {(Object.keys(ASPECT_LABEL) as CaptionAspect[]).map((key) => (
              <option key={key} value={key}>
                {ASPECT_LABEL[key]}
              </option>
            ))}
          </SelectInput>
        )}
      </Field>
    </div>
  );
}
