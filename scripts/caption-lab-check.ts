/**
 * Teste local da lógica de legendas (roda com: bun scripts/caption-lab-check.ts).
 * Valida as mesmas invariantes que o backend precisa respeitar.
 */
import {
  ASPECTS,
  DEMO_SRT,
  buildAss,
  diagnose,
  groupWords,
  hexRgbToAss,
  assTimestamp,
  linesFromSrt,
  linesFromWords,
  clampWordsPerLine,
  parseSrt,
  parseTimestamp,
  PRESETS,
  spreadWords,
  wordsFromPlainText,
} from "../src/lib/caption-lab";

let failures = 0;
function check(name: string, condition: boolean, detail = "") {
  const status = condition ? "PASS" : "FAIL";
  if (!condition) failures += 1;
  console.log(`${status}  ${name}${detail ? ` — ${detail}` : ""}`);
}

// 1. Parsing de timestamps
check("parseTimestamp 00:00:02,400 = 2.4", Math.abs(parseTimestamp("00:00:02,400") - 2.4) < 1e-6);
check("parseTimestamp 01:02:03.050", Math.abs(parseTimestamp("01:02:03.050") - 3723.05) < 1e-6);

// 2. SRT → linhas
const srtLines = parseSrt(DEMO_SRT);
check("SRT gera 3 linhas", srtLines.length === 3, `${srtLines.length}`);
check("primeira linha começa em 0", srtLines[0].start === 0);
check("última palavra fecha no fim do bloco", srtLines[0].words.at(-1)!.end === 2.4);
check(
  "linha crua de SRT estoura 42 caracteres (por isso precisa reagrupar)",
  srtLines.some((l) => l.words.map((w) => w.text).join(" ").length > 42),
);
check("clampWordsPerLine respeita 1..10", clampWordsPerLine(0) === 1 && clampWordsPerLine(99) === 10);

// 3. Distribuição proporcional
const spread = spreadWords("um palavrão gigantesco", 0, 3);
check("spreadWords mantém ordem e cobre o intervalo", spread[0].start === 0 && spread.at(-1)!.end === 3);
check(
  "palavra maior recebe mais tempo",
  spread[1].end - spread[1].start > spread[0].end - spread[0].start,
);

// 4. Agrupamento
const words = spreadWords("um dois tres quatro cinco seis", 0, 6);
const grouped = groupWords(words, { maxWords: 3 });
check("groupWords respeita maxWords", grouped.every((l) => l.words.length <= 3), `${grouped.length} linhas`);
const sentence = spreadWords("acabou. comeca de novo", 0, 4);
check("quebra após pontuação final", groupWords(sentence, { maxWords: 10 }).length === 2);
const gapWords = [
  { start: 0, end: 0.4, text: "antes" },
  { start: 2.0, end: 2.4, text: "depois" },
];
check("quebra em pausa > 0.65s", groupWords(gapWords, { maxWords: 10 }).length === 2);
check(
  "nunca passa de 42 caracteres por linha",
  groupWords(spreadWords("palavra ".repeat(12).trim(), 0, 12), { maxWords: 20 }).every(
    (l) => l.words.map((w) => w.text).join(" ").length <= 42,
  ),
);

// 5. Correção de sobreposição
const overlapping = [
  { start: 0, end: 1.2, text: "um" },
  { start: 0.8, end: 1.6, text: "dois" },
];
const fixed = linesFromWords(overlapping, 5).flatMap((l) => l.words);
check("linesFromWords corrige sobreposição", fixed[0].end <= fixed[1].start + 1e-9);

// 6. Cores
check("hexRgbToAss inverte para BBGGRR", hexRgbToAss("#FFE500") === "00E5FF");
check("hex inválido devolve vazio", hexRgbToAss("xyz") === "");

// 7. Timestamp ASS
check("assTimestamp 3723.05", assTimestamp(3723.05) === "1:02:03.05", assTimestamp(3723.05));

// 8. ASS por preset e por formato (pipeline real: SRT -> palavras -> group_words)
for (const preset of PRESETS) {
  const lines = linesFromSrt(DEMO_SRT, preset.wordsPerLine);
  for (const [aspect, dim] of Object.entries(ASPECTS)) {
    const built = buildAss(lines, {
      presetId: preset.id,
      videoWidth: dim.w,
      videoHeight: dim.h,
      position: "bottom",
      fontScale: 1,
    });
    const okHeader = built.ass.includes("[Events]") && built.ass.includes(`PlayResY: ${dim.h}`);
    const okEvents = built.events.length > 0 && built.ass.includes("Dialogue: 0,");
    const balanced = (built.ass.match(/\{/g) ?? []).length === (built.ass.match(/\}/g) ?? []).length;
    const failed = diagnose(lines, built, aspect as keyof typeof ASPECTS).filter((c) => !c.ok);
    check(
      `preset ${preset.id} @ ${aspect}`,
      okHeader && okEvents && balanced && failed.length === 0,
      failed.map((f) => f.label).join(", ") || `${built.events.length} eventos`,
    );
  }
}

// 9. font_scale mínimo (0.35) continua legível
const baseLines = linesFromSrt(DEMO_SRT, 3);
const tiny = buildAss(baseLines, { presetId: "hormozi", videoWidth: 1080, videoHeight: 1920, fontScale: 0.35 });
const big = buildAss(baseLines, { presetId: "hormozi", videoWidth: 1080, videoHeight: 1920, fontScale: 1.8 });
check("font_scale 0.35 reduz a fonte", tiny.style.fontSize < big.style.fontSize, `${tiny.style.fontSize} vs ${big.style.fontSize}`);
check("font_scale mínimo ainda > 12px", tiny.style.fontSize > 12, `${tiny.style.fontSize}px`);

// 10. Posições
check("center usa alignment 5", buildAss(baseLines, { presetId: "clean", videoWidth: 1080, videoHeight: 1920, position: "center" }).style.align === 5);
check("top usa alignment 8", buildAss(baseLines, { presetId: "clean", videoWidth: 1080, videoHeight: 1920, position: "top" }).style.align === 8);

// 11. Texto corrido sem timestamps
const plain = wordsFromPlainText("teste de narração sem timestamps nenhum", 8);
check("texto corrido vira palavras cronometradas", plain.length === 6 && plain.at(-1)!.end === 8);

// 12. Animações especiais
const kara = buildAss(linesFromSrt(DEMO_SRT, 5), { presetId: "karaoke", videoWidth: 1080, videoHeight: 1920 });
check("karaokê emite tags \\kf", kara.ass.includes("\\kf"));
const typed = buildAss(baseLines, { presetId: "hormozi", videoWidth: 1080, videoHeight: 1920, animation: "typewriter" });
check("typewriter esconde o resto com \\alpha&HFF&", typed.ass.includes("\\alpha&HFF&"));
const pop = buildAss(baseLines, { presetId: "hormozi", videoWidth: 1080, videoHeight: 1920, animation: "pop" });
check("pop reseta o estilo após a palavra ativa", pop.ass.includes("{\\r}"));

console.log(failures === 0 ? "\nTODOS OS TESTES PASSARAM" : `\n${failures} TESTE(S) FALHARAM`);
if (failures) process.exit(1);
