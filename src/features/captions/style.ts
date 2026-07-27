import type { CaptionAnimation } from "./api";

/**
 * Estado de estilo do editor de legendas — espelha exatamente os campos
 * aceitos por `POST /api/legendar/run` no backend Flask do aaPanel.
 */
/** Formato do palco: automático (lê o vídeo), retrato 9:16 ou paisagem 16:9. */
export type CaptionAspect = "auto" | "9:16" | "16:9" | "1:1";

export const ASPECT_LABEL: Record<CaptionAspect, string> = {
  auto: "Auto — detecta pelo vídeo",
  "9:16": "Retrato 9:16 (Reels/TikTok/Shorts)",
  "16:9": "Paisagem 16:9 (YouTube/TV)",
  "1:1": "Quadrado 1:1 (Feed)",
};

export const ASPECT_RATIO: Record<Exclude<CaptionAspect, "auto">, number> = {
  "9:16": 9 / 16,
  "16:9": 16 / 9,
  "1:1": 1,
};

/** Escolhe o formato mais próximo a partir das dimensões reais do vídeo. */
export function detectAspect(width: number, height: number): Exclude<CaptionAspect, "auto"> {
  if (!width || !height) return "9:16";
  const ratio = width / height;
  if (ratio > 1.15) return "16:9";
  if (ratio < 0.85) return "9:16";
  return "1:1";
}

export type CaptionStyle = {
  preset: string;
  animation: CaptionAnimation;
  wordsPerLine: number;
  fontScale: number;
  uppercase: boolean;
  emoji: boolean;
  accent: string;
  primary: string;
  /** Posição vertical do bloco de legenda no palco, 0 (topo) → 100 (base). */
  yPct: number;
  /** Formato do palco escolhido pelo usuário. */
  aspect: CaptionAspect;
  /** Encaixa cada palavra na batida da música do próprio vídeo (services/beatsync.py). */
  beatSync: boolean;
};

export const DEFAULT_STYLE: CaptionStyle = {
  preset: "hormozi",
  animation: "auto",
  wordsPerLine: 3,
  fontScale: 1,
  uppercase: true,
  emoji: false,
  accent: "",
  primary: "",
  yPct: 82,
  aspect: "auto",
  beatSync: false,
};

export type CaptionPosition = "top" | "center" | "bottom";

export function positionFromY(yPct: number): CaptionPosition {
  if (yPct <= 33) return "top";
  if (yPct <= 66) return "center";
  return "bottom";
}

export function marginRatioFromY(yPct: number): number {
  const pos = positionFromY(yPct);
  const raw = pos === "top" ? yPct / 100 : pos === "bottom" ? (100 - yPct) / 100 : 0.14;
  return Math.min(0.45, Math.max(0.02, Number(raw.toFixed(3))));
}

export function yFromPosition(pos: CaptionPosition, marginRatio = 0.14): number {
  if (pos === "top") return Math.round(marginRatio * 100);
  if (pos === "center") return 50;
  return Math.round(100 - marginRatio * 100);
}

export const POSITION_LABEL: Record<CaptionPosition, string> = {
  top: "Superior",
  center: "Centro",
  bottom: "Inferior (safe area)",
};

/** Aplica o estilo do editor sobre um FormData já montado pelo formulário. */
export function applyStyle(form: FormData, style: CaptionStyle): FormData {
  form.set("preset", style.preset);
  form.set("animation", style.animation);
  form.set("position", positionFromY(style.yPct));
  form.set("margin_ratio", marginRatioFromY(style.yPct).toFixed(3));
  form.set("words_per_line", String(style.wordsPerLine));
  form.set("font_scale", style.fontScale.toFixed(2));
  form.set("uppercase", style.uppercase ? "1" : "0");
  form.set("emoji", style.emoji ? "1" : "0");
  form.set("aspect", style.aspect);
  form.set("beat_sync", style.beatSync ? "1" : "0");
  if (style.accent) form.set("accent", style.accent);
  if (style.primary) form.set("primary", style.primary);
  return form;
}
