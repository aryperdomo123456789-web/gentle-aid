import { apiGet } from "@/lib/api";

export type CaptionAnimation =
  | "auto"
  | "none"
  | "pop"
  | "bounce"
  | "fade"
  | "karaoke"
  | "typewriter"
  | "highlight"
  | "boxed"
  | "shake"
  | "beat"
  | "zoom"
  | "slide"
  | "blur"
  | "wave"
  | "glitch"
  | "neon"
  | "rainbow"
  | "stamp"
  | "flip";

export type CaptionPreview = {
  bg: string;
  color: string;
  accent: string;
  weight: number;
  italic: boolean;
  boxed: boolean;
};

export type CaptionPreset = {
  id: string;
  label: string;
  tag: string;
  description: string;
  animation: CaptionAnimation;
  uppercase: boolean;
  words_per_line: number;
  preview: CaptionPreview;
};

export type CaptionCatalog = {
  presets: CaptionPreset[];
  animations: CaptionAnimation[];
  positions: string[];
  transcription: boolean;
};

export const ANIMATION_LABELS: Record<CaptionAnimation, string> = {
  auto: "Automático (do preset)",
  pop: "Pop — estoura a palavra ativa",
  bounce: "Bounce — quica verticalmente",
  shake: "Shake — sacudida estilo HQ",
  highlight: "Highlight — só troca a cor",
  boxed: "Boxed — caixa atrás da palavra",
  karaoke: "Karaokê — preenche acompanhando o áudio",
  typewriter: "Typewriter — revela e mantém",
  fade: "Fade — frase inteira suave",
  none: "Estático — sem animação",
  beat: "Beat — pulso na batida da música",
  zoom: "Zoom punch — entra grande e crava",
  slide: "Slide up — sobe deslizando",
  blur: "Blur in — desfoque que entra em foco",
  wave: "Wave — onda subindo e descendo",
  glitch: "Glitch — split RGB estilo falha",
  neon: "Neon pulse — brilho pulsante",
  rainbow: "Rainbow — ciclo de cores por palavra",
  stamp: "Stamp — carimbo que gira e crava",
  flip: "Flip 3D — vira no eixo Y",
};

export function fetchCaptionCatalog(signal?: AbortSignal) {
  return apiGet<CaptionCatalog>("/api/legendar/presets", signal);
}
