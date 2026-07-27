/**
 * Linha do tempo de pré-visualização — replica no navegador a mesma
 * distribuição de palavras que o backend faz (`captions.spread_words` /
 * `group_words`), para que o que você vê no editor seja o que é queimado
 * no vídeo pelo FFmpeg.
 */
export type PreviewWord = { text: string; start: number; end: number };
export type PreviewBlock = { start: number; end: number; words: PreviewWord[] };

export const SAMPLE_SCRIPT =
  "Se você chegou até aqui não pula essa parte porque o que eu vou mostrar agora muda o jogo do seu conteúdo em menos de sete dias";

const SRT_TIME = /(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/g;

function toSeconds(h: string, m: string, s: string, ms: string) {
  return Number(h) * 3600 + Number(m) * 60 + Number(s) + Number(ms) / 1000;
}

/** Extrai palavras com tempo a partir de um SRT colado pelo usuário. */
function wordsFromSrt(text: string): PreviewWord[] {
  const out: PreviewWord[] = [];
  const blocks = text.split(/\n\s*\n/);
  for (const block of blocks) {
    const lines = block.split("\n").filter(Boolean);
    const timeLine = lines.find((l) => l.includes("-->"));
    if (!timeLine) continue;
    const stamps = [...timeLine.matchAll(SRT_TIME)];
    if (stamps.length < 2) continue;
    const start = toSeconds(stamps[0][1], stamps[0][2], stamps[0][3], stamps[0][4]);
    const end = toSeconds(stamps[1][1], stamps[1][2], stamps[1][3], stamps[1][4]);
    const content = lines.filter((l) => l !== timeLine && !/^\d+$/.test(l.trim())).join(" ");
    const words = content.split(/\s+/).filter(Boolean);
    if (!words.length || end <= start) continue;
    const step = (end - start) / words.length;
    words.forEach((w, i) => out.push({ text: w, start: start + i * step, end: start + (i + 1) * step }));
  }
  return out;
}

/** Espalha um texto simples uniformemente ao longo da duração informada. */
function spreadWords(text: string, duration: number): PreviewWord[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const step = Math.max(0.12, duration / words.length);
  return words.map((w, i) => ({ text: w, start: i * step, end: (i + 1) * step }));
}

export function buildWords(transcript: string, duration: number): PreviewWord[] {
  const text = transcript.trim();
  if (text.includes("-->")) {
    const parsed = wordsFromSrt(text);
    if (parsed.length) return parsed;
  }
  return spreadWords(text || SAMPLE_SCRIPT, Math.max(3, duration));
}

export function groupWords(words: PreviewWord[], maxWords: number): PreviewBlock[] {
  const blocks: PreviewBlock[] = [];
  for (let i = 0; i < words.length; i += maxWords) {
    const chunk = words.slice(i, i + maxWords);
    if (!chunk.length) continue;
    blocks.push({ start: chunk[0].start, end: chunk[chunk.length - 1].end, words: chunk });
  }
  return blocks;
}

export function blockAt(blocks: PreviewBlock[], time: number): PreviewBlock | null {
  for (const block of blocks) {
    if (time >= block.start && time <= block.end) return block;
  }
  return null;
}

export function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
