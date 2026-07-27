/**
 * Laboratório local de legendas — porta fiel da lógica de
 * `backend/app/services/captions.py` para TypeScript.
 *
 * Objetivo: rodar a MESMA matemática de agrupamento, timing e geração de ASS
 * aqui dentro do Lovable (sem FFmpeg, sem aaPanel), para conseguir prever a
 * legenda antes de queimar o vídeo e para provar a lógica com testes.
 *
 * Regra de ouro: se algo mudar aqui, tem que mudar igual no Python — e
 * vice-versa. As funções abaixo são puras de propósito.
 */

export type Word = { start: number; end: number; text: string };
export type Line = { start: number; end: number; words: Word[] };

export type Animation =
  | "auto"
  | "none"
  | "pop"
  | "bounce"
  | "fade"
  | "karaoke"
  | "typewriter"
  | "highlight"
  | "boxed"
  | "shake";

export type Position = "bottom" | "center" | "top";

export const ANIMATIONS: Animation[] = [
  "auto",
  "none",
  "pop",
  "bounce",
  "fade",
  "karaoke",
  "typewriter",
  "highlight",
  "boxed",
  "shake",
];

export const POSITIONS: Record<Position, number> = { bottom: 2, center: 5, top: 8 };

export type Preset = {
  id: string;
  label: string;
  tag: string;
  /** fração da altura do vídeo (0.058 ≈ 111px em 1920 de altura) */
  size: number;
  /** cores no formato BBGGRR (ordem do ASS), igual ao Python */
  primary: string;
  accent: string;
  outline: string;
  back: string;
  bold: boolean;
  italic?: boolean;
  outlineW: number;
  shadow: number;
  borderStyle: number;
  uppercase: boolean;
  wordsPerLine: number;
  animation: Animation;
  spacing: number;
  fonts: string[];
  /** cores em RGB para o preview HTML */
  preview: { bg: string; color: string; accent: string; weight: number; italic: boolean; boxed: boolean };
};

export const PRESETS: Preset[] = [
  {
    id: "hormozi",
    label: "Hormozi",
    tag: "Talking head · nº1 do mercado",
    size: 0.058,
    primary: "FFFFFF",
    accent: "00E5FF",
    outline: "000000",
    back: "000000",
    bold: true,
    outlineW: 6,
    shadow: 3,
    borderStyle: 1,
    uppercase: true,
    wordsPerLine: 3,
    animation: "pop",
    spacing: 0.5,
    fonts: ["Montserrat ExtraBold", "Montserrat", "Anton", "DejaVu Sans"],
    preview: { bg: "#0b0b0f", color: "#ffffff", accent: "#ffe500", weight: 900, italic: false, boxed: false },
  },
  {
    id: "beast",
    label: "MrBeast",
    tag: "Máxima energia",
    size: 0.066,
    primary: "FFFFFF",
    accent: "2BE2FF",
    outline: "000000",
    back: "000000",
    bold: true,
    outlineW: 8,
    shadow: 4,
    borderStyle: 1,
    uppercase: true,
    wordsPerLine: 2,
    animation: "bounce",
    spacing: 0.8,
    fonts: ["Impact", "Anton", "Montserrat ExtraBold", "DejaVu Sans"],
    preview: { bg: "#101017", color: "#ffffff", accent: "#ffe22b", weight: 900, italic: false, boxed: false },
  },
  {
    id: "karaoke",
    label: "Karaokê Musical",
    tag: "Acompanha a música",
    size: 0.052,
    primary: "FFFFFF",
    accent: "FF4BD8",
    outline: "1A0022",
    back: "000000",
    bold: true,
    outlineW: 5,
    shadow: 2,
    borderStyle: 1,
    uppercase: false,
    wordsPerLine: 5,
    animation: "karaoke",
    spacing: 0.3,
    fonts: ["Montserrat", "DejaVu Sans"],
    preview: { bg: "#150019", color: "#ffffff", accent: "#d84bff", weight: 800, italic: false, boxed: false },
  },
  {
    id: "clean",
    label: "Podcast Clean",
    tag: "Formato longo / 16:9",
    size: 0.042,
    primary: "FFFFFF",
    accent: "F5D5CB",
    outline: "000000",
    back: "000000",
    bold: false,
    outlineW: 3,
    shadow: 1,
    borderStyle: 1,
    uppercase: false,
    wordsPerLine: 8,
    animation: "fade",
    spacing: 0,
    fonts: ["Inter", "Montserrat", "DejaVu Sans"],
    preview: { bg: "#12151c", color: "#ffffff", accent: "#cbd5f5", weight: 600, italic: false, boxed: false },
  },
  {
    id: "golden",
    label: "Golden Frame",
    tag: "Luxo / finanças",
    size: 0.05,
    primary: "9FD8FF",
    accent: "00D7FF",
    outline: "0B0B0B",
    back: "000000",
    bold: true,
    italic: true,
    outlineW: 4,
    shadow: 2,
    borderStyle: 1,
    uppercase: false,
    wordsPerLine: 5,
    animation: "highlight",
    spacing: 0.4,
    fonts: ["Playfair Display", "Montserrat", "DejaVu Serif", "DejaVu Sans"],
    preview: { bg: "#15100a", color: "#ffd89f", accent: "#ffd700", weight: 700, italic: true, boxed: false },
  },
  {
    id: "aqua",
    label: "Aqua Edge",
    tag: "Lifestyle / viagem",
    size: 0.05,
    primary: "FFFFFF",
    accent: "FFE55C",
    outline: "5A1E00",
    back: "000000",
    bold: true,
    outlineW: 5,
    shadow: 2,
    borderStyle: 1,
    uppercase: true,
    wordsPerLine: 3,
    animation: "pop",
    spacing: 0.4,
    fonts: ["Montserrat", "DejaVu Sans"],
    preview: { bg: "#04141c", color: "#ffffff", accent: "#5ce5ff", weight: 800, italic: false, boxed: false },
  },
  {
    id: "comic",
    label: "Comic Burst",
    tag: "Humor / reação",
    size: 0.06,
    primary: "FFFFFF",
    accent: "2B2BFF",
    outline: "000000",
    back: "000000",
    bold: true,
    outlineW: 7,
    shadow: 3,
    borderStyle: 1,
    uppercase: true,
    wordsPerLine: 2,
    animation: "shake",
    spacing: 0.8,
    fonts: ["Comic Neue", "Impact", "DejaVu Sans"],
    preview: { bg: "#1a0c0c", color: "#ffffff", accent: "#ff2b2b", weight: 900, italic: false, boxed: false },
  },
];

const LEGACY_ALIASES: Record<string, string> = { viral: "hormozi", clean: "clean", neon: "neon", karaoke: "karaoke" };

export function resolvePreset(presetId?: string | null): Preset {
  const key = LEGACY_ALIASES[(presetId ?? "").trim().toLowerCase()] ?? (presetId ?? "").trim().toLowerCase();
  return PRESETS.find((p) => p.id === key) ?? PRESETS[0];
}

/* ------------------------------------------------------------------ */
/* Entrada: SRT                                                        */
/* ------------------------------------------------------------------ */
const TS_RE = /(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})/;

export function parseTimestamp(value: string): number {
  const m = TS_RE.exec(value);
  if (!m) return 0;
  const [, h, mm, ss, ms] = m;
  return Number(h) * 3600 + Number(mm) * 60 + Number(ss) + Number(ms.padEnd(3, "0")) / 1000;
}

/** Distribui o tempo da linha entre as palavras, proporcional ao nº de caracteres. */
export function spreadWords(text: string, start: number, end: number): Word[] {
  const tokens = text.split(/\s+/).filter(Boolean);
  if (!tokens.length) return [];
  const totalChars = tokens.reduce((acc, t) => acc + t.length, 0) || 1;
  const span = Math.max(0.2, end - start);
  const words: Word[] = [];
  let cursor = start;
  for (const token of tokens) {
    const share = span * (token.length / totalChars);
    words.push({ start: cursor, end: Math.min(end, cursor + share), text: token });
    cursor += share;
  }
  words[words.length - 1].end = end;
  return words;
}

export function parseSrt(text: string): Line[] {
  const lines: Line[] = [];
  for (const block of text.trim().split(/\n\s*\n/)) {
    let rows = block
      .split("\n")
      .map((r) => r.trim())
      .filter(Boolean);
    if (!rows.length) continue;
    if (/^\d+$/.test(rows[0])) rows = rows.slice(1);
    if (!rows.length || !rows[0].includes("-->")) continue;
    const [left, right] = rows[0].split("-->");
    const start = parseTimestamp(left);
    const end = parseTimestamp(right ?? "");
    const content = rows.slice(1).join(" ").trim();
    if (!content || end <= start) continue;
    lines.push({ start, end, words: spreadWords(content, start, end) });
  }
  return lines;
}

/** Texto corrido sem timestamps: distribui numa duração alvo (ritmo de fala). */
export function wordsFromPlainText(text: string, duration: number): Word[] {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!clean) return [];
  return spreadWords(clean, 0, Math.max(1, duration));
}

/* ------------------------------------------------------------------ */
/* Agrupamento                                                         */
/* ------------------------------------------------------------------ */
export function groupWords(
  words: Word[],
  { maxWords, maxChars = 42, maxGap = 0.65 }: { maxWords: number; maxChars?: number; maxGap?: number },
): Line[] {
  const lines: Line[] = [];
  let bucket: Word[] = [];
  const flush = () => {
    if (bucket.length) {
      lines.push({ start: bucket[0].start, end: bucket[bucket.length - 1].end, words: bucket });
      bucket = [];
    }
  };
  for (const word of words) {
    if (bucket.length) {
      const last = bucket[bucket.length - 1];
      const gap = word.start - last.end;
      const chars = bucket.reduce((acc, w) => acc + w.text.length + 1, 0) + word.text.length;
      const endsSentence = /[.!?…]$/.test(last.text);
      if (bucket.length >= maxWords || chars > maxChars || gap > maxGap || endsSentence) flush();
    }
    bucket.push(word);
  }
  flush();
  return lines;
}

/**
 * PIPELINE CORRETO DO SRT (igual ao blueprint `legendar.py`):
 * parse_srt → achata as palavras → group_words(max_words).
 * Usar as linhas cruas do SRT direto no ASS é o erro clássico: elas vêm com
 * frases inteiras (>42 caracteres) e ignoram o `words_per_line` do preset.
 */
export function linesFromSrt(text: string, maxWords: number): Line[] {
  const words = parseSrt(text).flatMap((line) => line.words);
  return groupWords(words, { maxWords: clampWordsPerLine(maxWords) });
}

/** O backend aceita apenas 1..10 palavras por linha. */
export function clampWordsPerLine(value: number): number {
  return Math.max(1, Math.min(10, Math.round(value || 1)));
}

/** Ordena, corrige sobreposição e agrupa — espelho de `lines_from_segments`. */

export function linesFromWords(words: Word[], maxWords: number): Line[] {
  const list = words.filter((w) => w.text.trim()).sort((a, b) => a.start - b.start);
  for (let i = 0; i < list.length - 1; i += 1) {
    if (list[i].end > list[i + 1].start) {
      list[i].end = Math.max(list[i].start + 0.08, list[i + 1].start);
    }
  }
  return groupWords(list, { maxWords });
}

/* ------------------------------------------------------------------ */
/* Cores e tempo                                                       */
/* ------------------------------------------------------------------ */
export function hexRgbToAss(value: string): string {
  const raw = (value || "").trim().replace(/^#/, "");
  if (!/^[0-9A-Fa-f]{6}$/.test(raw)) return "";
  return (raw.slice(4, 6) + raw.slice(2, 4) + raw.slice(0, 2)).toUpperCase();
}

/** BBGGRR → #RRGGBB, para pintar o preview HTML com a cor real do ASS. */
export function assToCssHex(value: string): string {
  const raw = (value || "").trim().replace(/^#/, "");
  if (!/^[0-9A-Fa-f]{6}$/.test(raw)) return "#ffffff";
  return `#${(raw.slice(4, 6) + raw.slice(2, 4) + raw.slice(0, 2)).toLowerCase()}`;
}

export function assColor(value: string, alpha = "00"): string {
  const raw = (value || "").trim().replace(/^#/, "");
  const safe = /^[0-9A-Fa-f]{6}$/.test(raw) ? raw.toUpperCase() : "FFFFFF";
  return `&H${alpha}${safe}&`;
}

export function assTimestamp(seconds: number): string {
  const clamped = Math.max(0, seconds);
  let cs = Math.round(clamped * 100);
  const h = Math.floor(cs / 360000);
  cs -= h * 360000;
  const m = Math.floor(cs / 6000);
  cs -= m * 6000;
  const s = Math.floor(cs / 100);
  cs -= s * 100;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(cs).padStart(2, "0")}`;
}

function escapeText(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/\{/g, "(").replace(/\}/g, ")").replace(/\n/g, "\\N");
}

/* ------------------------------------------------------------------ */
/* Eventos                                                             */
/* ------------------------------------------------------------------ */
export type CaptionEvent = {
  start: number;
  end: number;
  /** palavras da linha, na ordem */
  words: string[];
  /** índice da palavra ativa (-1 = linha inteira) */
  activeIndex: number;
  text: string;
  ass: string;
};

function activeTag(anim: Animation, accent: string): string {
  const color = `\\c${accent}`;
  if (anim === "pop") return `{${color}\\fscx118\\fscy118\\t(0,110,\\fscx100\\fscy100)}`;
  if (anim === "bounce") return `{${color}\\fscy132\\fscx108\\t(0,90,\\fscy96\\fscx104)\\t(90,180,\\fscy100\\fscx100)}`;
  if (anim === "shake")
    return `{${color}\\frz-4\\t(0,80,\\frz4)\\t(80,160,\\frz0)\\fscx112\\fscy112\\t(0,140,\\fscx100\\fscy100)}`;
  if (anim === "boxed") return `{\\c&H00FFFFFF&\\3c${accent}\\bord14\\shad0}`;
  return `{${color}}`;
}

export function buildEvents(
  lines: Line[],
  { animation, uppercase, accent }: { animation: Animation; uppercase: boolean; accent: string },
): CaptionEvent[] {
  const out: CaptionEvent[] = [];
  const render = (t: string) => escapeText(uppercase ? t.toUpperCase() : t);

  for (const line of lines) {
    const words = line.words;
    if (!words.length) continue;
    const raw = words.map((w) => (uppercase ? w.text.toUpperCase() : w.text));

    if (animation === "none" || animation === "fade") {
      const tag = animation === "fade" ? "{\\fad(120,120)}" : "";
      out.push({
        start: line.start,
        end: line.end,
        words: raw,
        activeIndex: -1,
        text: raw.join(" "),
        ass: `Dialogue: 0,${assTimestamp(line.start)},${assTimestamp(line.end)},Viral,,0,0,0,,${tag}${words
          .map((w) => render(w.text))
          .join(" ")}`,
      });
      continue;
    }

    if (animation === "karaoke") {
      const chunks = words.map((w) => `{\\kf${Math.max(5, Math.round((w.end - w.start) * 100))}}${render(w.text)}`);
      out.push({
        start: line.start,
        end: line.end,
        words: raw,
        activeIndex: -1,
        text: raw.join(" "),
        ass: `Dialogue: 0,${assTimestamp(line.start)},${assTimestamp(line.end)},Viral,,0,0,0,,{\\fad(60,60)}${chunks.join(" ")}`,
      });
      continue;
    }

    if (animation === "typewriter") {
      words.forEach((word, index) => {
        const visible = words.slice(0, index + 1).map((w) => render(w.text));
        const hidden = words.slice(index + 1).map((w) => render(w.text));
        const text = visible.join(" ") + (hidden.length ? ` {\\alpha&HFF&}${hidden.join(" ")}` : "");
        const stop = index + 1 < words.length ? words[index + 1].start : line.end;
        const end = Math.max(word.start + 0.06, stop);
        out.push({
          start: word.start,
          end,
          words: raw.slice(0, index + 1),
          activeIndex: index,
          text: raw.slice(0, index + 1).join(" "),
          ass: `Dialogue: 0,${assTimestamp(word.start)},${assTimestamp(end)},Viral,,0,0,0,,${text}`,
        });
      });
      continue;
    }

    // pop, bounce, highlight, boxed, shake — palavra a palavra
    words.forEach((word, index) => {
      const parts = words.map((other, otherIndex) => {
        const token = render(other.text);
        return otherIndex === index ? `${activeTag(animation, accent)}${token}{\\r}` : token;
      });
      const stop = index + 1 < words.length ? words[index + 1].start : line.end;
      const end = Math.max(word.start + 0.08, stop);
      out.push({
        start: word.start,
        end,
        words: raw,
        activeIndex: index,
        text: raw.join(" "),
        ass: `Dialogue: 0,${assTimestamp(word.start)},${assTimestamp(end)},Viral,,0,0,0,,${parts.join(" ")}`,
      });
    });
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* ASS completo                                                        */
/* ------------------------------------------------------------------ */
export type BuildOptions = {
  presetId: string;
  videoWidth: number;
  videoHeight: number;
  position?: Position;
  animation?: Animation;
  uppercase?: boolean | null;
  fontScale?: number;
  accentHex?: string;
  primaryHex?: string;
  marginRatio?: number;
};

export type BuildResult = {
  ass: string;
  events: CaptionEvent[];
  style: {
    font: string;
    fontSize: number;
    align: number;
    marginV: number;
    marginH: number;
    animation: Animation;
    uppercase: boolean;
    primaryCss: string;
    accentCss: string;
    outlineCss: string;
    outlineW: number;
  };
};

export function buildAss(lines: Line[], options: BuildOptions): BuildResult {
  const preset = resolvePreset(options.presetId);
  const width = Math.max(64, Math.trunc(options.videoWidth || 1080));
  const height = Math.max(64, Math.trunc(options.videoHeight || 1920));
  const requested = options.animation ?? "auto";
  const anim: Animation = requested !== "auto" && ANIMATIONS.includes(requested) ? requested : preset.animation;
  const upper = options.uppercase === null || options.uppercase === undefined ? preset.uppercase : !!options.uppercase;

  const font = preset.fonts[0];
  const fontScale = Math.max(0.35, Math.min(1.8, options.fontScale ?? 1));
  const size = Math.max(12, Math.trunc(height * preset.size * Math.max(0.5, Math.min(2, fontScale))));
  const align = POSITIONS[options.position ?? "bottom"] ?? 2;
  const marginRatio = options.marginRatio ?? 0.14;
  const marginV = align === 5 ? 10 : Math.trunc(height * (align === 2 ? marginRatio : 0.08));
  const marginH = Math.trunc(width * 0.06);

  const primaryRaw = hexRgbToAss(options.primaryHex ?? "") || preset.primary;
  const accentRaw = hexRgbToAss(options.accentHex ?? "") || preset.accent;
  const primary = assColor(primaryRaw);
  const accent = assColor(accentRaw);
  const outline = assColor(preset.outline);
  const back = assColor(preset.back, preset.borderStyle === 4 ? "40" : "80");

  const header = [
    "[Script Info]",
    "ScriptType: v4.00+",
    "WrapStyle: 2",
    "ScaledBorderAndShadow: yes",
    "YCbCr Matrix: TV.709",
    `PlayResX: ${width}`,
    `PlayResY: ${height}`,
    "",
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour," +
      " Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline," +
      " Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    `Style: Viral,${font},${size},${primary},${accent},${outline},${back},` +
      `${preset.bold ? -1 : 0},${preset.italic ? -1 : 0},0,0,100,100,` +
      `${preset.spacing},0,${preset.borderStyle},${preset.outlineW},${preset.shadow},` +
      `${align},${marginH},${marginH},${marginV},1`,
    "",
    "[Events]",
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
  ];

  const events = buildEvents(lines, { animation: anim, uppercase: upper, accent });

  return {
    ass: [...header, ...events.map((e) => e.ass)].join("\n") + "\n",
    events,
    style: {
      font,
      fontSize: size,
      align,
      marginV,
      marginH,
      animation: anim,
      uppercase: upper,
      primaryCss: assToCssHex(primaryRaw),
      accentCss: assToCssHex(accentRaw),
      outlineCss: assToCssHex(preset.outline),
      outlineW: preset.outlineW,
    },
  };
}

/* ------------------------------------------------------------------ */
/* Diagnóstico — o que o laboratório checa                              */
/* ------------------------------------------------------------------ */
export type Check = { id: string; label: string; ok: boolean; detail: string };

export const ASPECTS: Record<string, { w: number; h: number; label: string }> = {
  "9:16": { w: 1080, h: 1920, label: "Vertical (Reels/Shorts/TikTok)" },
  "16:9": { w: 1920, h: 1080, label: "Deitado (YouTube)" },
  "1:1": { w: 1080, h: 1080, label: "Quadrado (Feed)" },
};

export function diagnose(lines: Line[], result: BuildResult, aspect: keyof typeof ASPECTS): Check[] {
  const checks: Check[] = [];
  const allWords = lines.flatMap((l) => l.words);

  let overlaps = 0;
  for (let i = 0; i < allWords.length - 1; i += 1) {
    if (allWords[i].end > allWords[i + 1].start + 0.001) overlaps += 1;
  }
  checks.push({
    id: "overlap",
    label: "Timings sem sobreposição",
    ok: overlaps === 0,
    detail: overlaps === 0 ? "Nenhuma palavra invade a próxima." : `${overlaps} palavra(s) sobrepostas.`,
  });

  const longest = lines.reduce((acc, l) => Math.max(acc, l.words.map((w) => w.text).join(" ").length), 0);
  checks.push({
    id: "chars",
    label: "Linha ≤ 42 caracteres",
    ok: longest <= 42,
    detail: `Maior linha tem ${longest} caracteres.`,
  });

  const tooFast = result.events.filter((e) => e.end - e.start < 0.08).length;
  checks.push({
    id: "minimum",
    label: "Nenhum evento abaixo de 80 ms",
    ok: tooFast === 0,
    detail: tooFast === 0 ? "Todos os eventos são legíveis pelo renderer." : `${tooFast} evento(s) muito curtos.`,
  });

  const { w, h } = ASPECTS[aspect];
  const ratio = result.style.fontSize / h;
  const safe = ratio >= 0.02 && ratio <= 0.12;
  checks.push({
    id: "size",
    label: "Corpo de fonte dentro da faixa segura",
    ok: safe,
    detail: `${result.style.fontSize}px em ${w}x${h} (${(ratio * 100).toFixed(1)}% da altura).`,
  });

  const bottomSafe = result.style.align !== 2 || result.style.marginV >= h * 0.1;
  checks.push({
    id: "safearea",
    label: "Margem fora da zona da UI do app",
    ok: bottomSafe,
    detail: `Margem vertical de ${result.style.marginV}px (recomendado ≥ ${Math.trunc(h * 0.1)}px embaixo).`,
  });

  checks.push({
    id: "events",
    label: "ASS gerado com eventos",
    ok: result.events.length > 0,
    detail: `${lines.length} linha(s) → ${result.events.length} evento(s) Dialogue.`,
  });

  return checks;
}

export const DEMO_SRT = `1
00:00:00,000 --> 00:00:02,400
Ninguém te conta isso sobre dinheiro.

2
00:00:02,600 --> 00:00:05,900
O algoritmo premia retenção, não beleza.

3
00:00:06,200 --> 00:00:09,000
Corta os três primeiros segundos e testa de novo.
`;
