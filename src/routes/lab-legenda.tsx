import { createFileRoute } from "@tanstack/react-router";
import { ClipboardCopy, FlaskConical, CircleCheck, CircleAlert, Pause, Play, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { TopNav } from "@/components/TopNav";
import {
  ANIMATIONS,
  ASPECTS,
  DEMO_SRT,
  PRESETS,
  buildAss,
  clampWordsPerLine,
  diagnose,
  linesFromSrt,
  linesFromWords,
  resolvePreset,
  wordsFromPlainText,
  type Animation,
  type Position,
} from "@/lib/caption-lab";

export const Route = createFileRoute("/lab-legenda")({
  head: () => ({
    meta: [
      { title: "Laboratório de Legendas - previsão local do ASS | Ecossistema Viral" },
      {
        name: "description",
        content:
          "Simule a legenda antes de queimar o vídeo: mesma lógica de agrupamento, timing e ASS do backend, com preview animado, diagnóstico e código gerado.",
      },
      { property: "og:title", content: "Laboratório de Legendas - Ecossistema Viral" },
      {
        property: "og:description",
        content: "Preveja o resultado da ferramenta de legenda com a lógica real do motor ASS, sem depender do servidor.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: CaptionLabPage,
});

type Source = "srt" | "texto";

function CaptionLabPage() {
  const [source, setSource] = useState<Source>("srt");
  const [srt, setSrt] = useState(DEMO_SRT);
  const [plain, setPlain] = useState(
    "Ninguem te conta isso sobre dinheiro. O algoritmo premia retencao, nao beleza. Corta os tres primeiros segundos e testa de novo.",
  );
  const [plainDuration, setPlainDuration] = useState(9);
  const [presetId, setPresetId] = useState("hormozi");
  const [animation, setAnimation] = useState<Animation>("auto");
  const [position, setPosition] = useState<Position>("bottom");
  const [aspect, setAspect] = useState<keyof typeof ASPECTS>("9:16");
  const [fontScale, setFontScale] = useState(1);
  const [wordsPerLine, setWordsPerLine] = useState<number | null>(null);
  const [uppercase, setUppercase] = useState<boolean | null>(null);
  const [playing, setPlaying] = useState(true);
  const [time, setTime] = useState(0);

  const preset = resolvePreset(presetId);
  const maxWords = clampWordsPerLine(wordsPerLine ?? preset.wordsPerLine);

  const lines = useMemo(() => {
    if (source === "srt") return linesFromSrt(srt, maxWords);
    return linesFromWords(wordsFromPlainText(plain, plainDuration), maxWords);
  }, [source, srt, plain, plainDuration, maxWords]);

  const dim = ASPECTS[aspect];
  const result = useMemo(
    () =>
      buildAss(lines, {
        presetId,
        videoWidth: dim.w,
        videoHeight: dim.h,
        position,
        animation,
        uppercase,
        fontScale,
      }),
    [lines, presetId, dim.w, dim.h, position, animation, uppercase, fontScale],
  );

  const checks = useMemo(() => diagnose(lines, result, aspect), [lines, result, aspect]);
  const duration = lines.length ? lines[lines.length - 1].end : 0;

  // Player local do preview
  const raf = useRef<number | null>(null);
  const startedAt = useRef(0);
  useEffect(() => {
    if (!playing || duration <= 0) return;
    startedAt.current = performance.now() - time * 1000;
    const tick = () => {
      const next = (performance.now() - startedAt.current) / 1000;
      setTime(next > duration + 0.4 ? 0 : next);
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, duration]);

  const current = result.events.find((e) => time >= e.start && time < e.end) ?? null;

  const previewHeight = aspect === "9:16" ? 460 : aspect === "1:1" ? 320 : 260;
  const previewWidth = (previewHeight * dim.w) / dim.h;
  const scale = previewHeight / dim.h;
  const fontPx = Math.max(9, result.style.fontSize * scale);
  const marginPx = result.style.marginV * scale;

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <main className="mx-auto w-full max-w-6xl px-3 py-6 sm:px-6 sm:py-10">
        <header className="mb-6 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-primary">
            <FlaskConical className="h-5 w-5" />
            <span className="text-xs font-semibold uppercase tracking-widest">Laboratório local</span>
          </div>
          <h1 className="text-2xl font-bold sm:text-3xl">Laboratório de Legendas</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Roda 100% aqui, sem FFmpeg e sem o aaPanel. Usa a mesma lógica do motor
            <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">captions.py</code>: agrupamento por pausa,
            distribuição de tempo por caractere e geração do ASS. Serve para provar o comportamento antes de queimar o
            vídeo em produção.
          </p>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,380px)]">
          {/* Coluna esquerda: entrada + controles */}
          <section className="space-y-5">
            <div className="rounded-xl border bg-card p-4">
              <div className="mb-3 flex flex-wrap gap-2">
                {(["srt", "texto"] as Source[]).map((item) => (
                  <button
                    key={item}
                    onClick={() => setSource(item)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                      source === item ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {item === "srt" ? "SRT com timestamps" : "Texto corrido"}
                  </button>
                ))}
              </div>
              {source === "srt" ? (
                <textarea
                  value={srt}
                  onChange={(e) => setSrt(e.target.value)}
                  spellCheck={false}
                  className="h-48 w-full resize-y rounded-lg border bg-background p-3 font-mono text-xs"
                />
              ) : (
                <div className="space-y-3">
                  <textarea
                    value={plain}
                    onChange={(e) => setPlain(e.target.value)}
                    spellCheck={false}
                    className="h-32 w-full resize-y rounded-lg border bg-background p-3 text-sm"
                  />
                  <label className="flex items-center gap-3 text-xs text-muted-foreground">
                    Duração simulada
                    <input
                      type="range"
                      min={2}
                      max={60}
                      value={plainDuration}
                      onChange={(e) => setPlainDuration(Number(e.target.value))}
                      className="flex-1"
                    />
                    <span className="w-12 text-right font-mono text-foreground">{plainDuration}s</span>
                  </label>
                </div>
              )}
            </div>

            <div className="rounded-xl border bg-card p-4">
              <h2 className="mb-3 text-sm font-semibold">Controles (mesmos parâmetros do backend)</h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Preset">
                  <select value={presetId} onChange={(e) => setPresetId(e.target.value)} className={selectCls}>
                    {PRESETS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label} · {p.tag}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Animação">
                  <select
                    value={animation}
                    onChange={(e) => setAnimation(e.target.value as Animation)}
                    className={selectCls}
                  >
                    {ANIMATIONS.map((a) => (
                      <option key={a} value={a}>
                        {a === "auto" ? `auto (${preset.animation})` : a}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Formato">
                  <select
                    value={aspect}
                    onChange={(e) => setAspect(e.target.value as keyof typeof ASPECTS)}
                    className={selectCls}
                  >
                    {Object.entries(ASPECTS).map(([id, v]) => (
                      <option key={id} value={id}>
                        {id} — {v.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Posição">
                  <select
                    value={position}
                    onChange={(e) => setPosition(e.target.value as Position)}
                    className={selectCls}
                  >
                    <option value="bottom">Embaixo</option>
                    <option value="center">Centro</option>
                    <option value="top">Em cima</option>
                  </select>
                </Field>
                <Field label={`Tamanho da fonte · ${fontScale.toFixed(2)}x (${result.style.fontSize}px)`}>
                  <input
                    type="range"
                    min={0.35}
                    max={1.8}
                    step={0.05}
                    value={fontScale}
                    onChange={(e) => setFontScale(Number(e.target.value))}
                    className="w-full"
                  />
                </Field>
                <Field label={`Palavras por linha · ${maxWords}`}>
                  <input
                    type="range"
                    min={1}
                    max={10}
                    value={maxWords}
                    onChange={(e) => setWordsPerLine(Number(e.target.value))}
                    className="w-full"
                  />
                </Field>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={uppercase === null ? preset.uppercase : uppercase}
                    onChange={(e) => setUppercase(e.target.checked)}
                  />
                  Caixa alta
                </label>
                <button
                  onClick={() => {
                    setUppercase(null);
                    setWordsPerLine(null);
                    setAnimation("auto");
                    setFontScale(1);
                  }}
                  className="inline-flex items-center gap-1 rounded-lg bg-muted px-2 py-1 font-medium"
                >
                  <RotateCcw className="h-3 w-3" /> Voltar ao preset
                </button>
              </div>
            </div>

            <div className="rounded-xl border bg-card p-4">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-semibold">ASS gerado ({result.events.length} eventos)</h2>
                <button
                  onClick={() => navigator.clipboard?.writeText(result.ass)}
                  className="inline-flex items-center gap-1 rounded-lg bg-muted px-2 py-1 text-xs font-medium"
                >
                  <ClipboardCopy className="h-3 w-3" /> Copiar
                </button>
              </div>
              <pre className="max-h-72 overflow-auto rounded-lg bg-muted/50 p-3 text-[11px] leading-relaxed">
                {result.ass}
              </pre>
            </div>
          </section>

          {/* Coluna direita: preview + diagnóstico */}
          <aside className="space-y-5">
            <div className="rounded-xl border bg-card p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Preview ({aspect})</h2>
                <button
                  onClick={() => setPlaying((p) => !p)}
                  className="inline-flex items-center gap-1 rounded-lg bg-muted px-2 py-1 text-xs font-medium"
                >
                  {playing ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                  {playing ? "Pausar" : "Tocar"}
                </button>
              </div>
              <div
                className="relative mx-auto overflow-hidden rounded-lg"
                style={{ width: previewWidth, height: previewHeight, background: preset.preview.bg }}
              >
                <div
                  className="absolute inset-x-2 flex justify-center text-center"
                  style={
                    result.style.align === 5
                      ? { top: "50%", transform: "translateY(-50%)" }
                      : result.style.align === 8
                        ? { top: marginPx }
                        : { bottom: marginPx }
                  }
                >
                  <span
                    style={{
                      fontSize: fontPx,
                      lineHeight: 1.15,
                      fontWeight: preset.preview.weight,
                      fontStyle: preset.italic ? "italic" : "normal",
                      color: result.style.primaryCss,
                      WebkitTextStroke: `${Math.max(1, result.style.outlineW * scale)}px ${result.style.outlineCss}`,
                      paintOrder: "stroke fill",
                      letterSpacing: `${preset.spacing * scale * 4}px`,
                    }}
                  >
                    {current
                      ? current.words.map((w, i) => (
                          <span
                            key={`${w}-${i}`}
                            style={{
                              color: i === current.activeIndex ? result.style.accentCss : undefined,
                              display: "inline-block",
                              transform: i === current.activeIndex && result.style.animation === "pop" ? "scale(1.12)" : undefined,
                              transition: "transform 110ms ease-out",
                              marginRight: "0.28em",
                            }}
                          >
                            {w}
                          </span>
                        ))
                      : null}
                  </span>
                </div>
              </div>
              <input
                type="range"
                min={0}
                max={Math.max(0.1, duration)}
                step={0.02}
                value={Math.min(time, duration)}
                onChange={(e) => {
                  setPlaying(false);
                  setTime(Number(e.target.value));
                }}
                className="mt-3 w-full"
              />
              <p className="text-center font-mono text-[11px] text-muted-foreground">
                {time.toFixed(2)}s / {duration.toFixed(2)}s
              </p>
            </div>

            <div className="rounded-xl border bg-card p-4">
              <h2 className="mb-3 text-sm font-semibold">Diagnóstico automático</h2>
              <ul className="space-y-2">
                {checks.map((c) => (
                  <li key={c.id} className="flex gap-2 text-xs">
                    {c.ok ? (
                      <CircleCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                    ) : (
                      <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                    )}
                    <span>
                      <span className="font-medium">{c.label}</span>
                      <span className="block text-muted-foreground">{c.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-xl border bg-card p-4">
              <h2 className="mb-2 text-sm font-semibold">Linhas montadas ({lines.length})</h2>
              <ul className="max-h-56 space-y-1 overflow-auto text-[11px] font-mono">
                {lines.map((l, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="shrink-0 text-muted-foreground">
                      {l.start.toFixed(2)}→{l.end.toFixed(2)}
                    </span>
                    <span>{l.words.map((w) => w.text).join(" ")}</span>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}

const selectCls = "w-full rounded-lg border bg-background px-2 py-1.5 text-xs";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
