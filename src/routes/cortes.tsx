import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import { DiscoveryPanel, type DiscoveryCard } from "@/components/DiscoveryPanel";
import { Field, FileDrop, SelectInput, TextInput } from "@/components/form";
import { JobSettingsGuard } from "@/components/JobSettingsGuard";
import { MutationSelect } from "@/components/MutationSelect";
import { ToolShell } from "@/components/ToolShell";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import { fetchClipOptions, type ClipOptions, type ClipResult } from "@/features/clips/api";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiPostForm, downloadUrl, friendlyError, type Job } from "@/lib/api";

export const Route = createFileRoute("/cortes")({
  head: () => ({
    meta: [
      { title: "Fábrica de Cortes — vídeo longo vira cortes virais legendados" },
      {
        name: "description",
        content:
          "Envie um vídeo longo ou um link: a IA acha os melhores momentos por nicho, corta em 9:16, legenda animada, mistura trilha e entrega tudo esterilizado.",
      },
      { property: "og:title", content: "Fábrica de Cortes — melhores momentos automáticos" },
      {
        property: "og:description",
        content:
          "Cortes inteligentes por nicho, legendas animadas, trilha com ducking e hash inédito em cada arquivo.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Cortes,
});

const RANGES = [
  { id: "shorts", label: "Shorts curtos · 20s a 60s", min: 20, max: 60 },
  { id: "padrao", label: "Padrão viral · 1 min a 3 min", min: 60, max: 180 },
  { id: "medio", label: "Médio · 3 min a 8 min", min: 180, max: 480 },
  { id: "longo", label: "Longo · 5 min a 15 min", min: 300, max: 900 },
  { id: "custom", label: "Personalizado (eu escolho)", min: 60, max: 180 },
];

function secondsLabel(value: number) {
  if (value < 60) return `${Math.round(value)}s`;
  const min = Math.floor(value / 60);
  const sec = Math.round(value % 60);
  return sec ? `${min}min ${sec}s` : `${min}min`;
}

/** Aceita "90", "1:30" ou "01:02:03" e devolve segundos. */
function parseTimecode(raw: string): number | null {
  const text = raw.trim().replace(",", ".");
  if (!text) return null;
  const parts = text.split(":").map((p) => Number(p));
  if (parts.some((p) => Number.isNaN(p) || p < 0)) return null;
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return null;
}

function toTimecode(seconds: number) {
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

type ManualSegment = { uid: string; start: string; end: string; title: string };

function newUid() {
  return Math.random().toString(36).slice(2, 9);
}

function segmentDurationLabel(seg: ManualSegment) {
  const start = parseTimecode(seg.start);
  const end = parseTimecode(seg.end);
  if (start === null || end === null || end <= start) return "—";
  return secondsLabel(end - start);
}

function Cortes() {
  const { job, error, busy, run, cancel, remove } = useJobRunner("clips");
  const [options, setOptions] = useState<ClipOptions | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [hasFile, setHasFile] = useState(false);
  const [card, setCard] = useState<DiscoveryCard | null>(null);
  const [range, setRange] = useState("padrao");
  const [minSeconds, setMinSeconds] = useState(60);
  const [maxSeconds, setMaxSeconds] = useState(180);
  const [aspect, setAspect] = useState("9:16");
  const [frame, setFrame] = useState("crop");
  const [manualOn, setManualOn] = useState(false);
  const [segments, setSegments] = useState<ManualSegment[]>([]);
  const [manualError, setManualError] = useState<string | null>(null);
  const [captionPreset, setCaptionPreset] = useState("hormozi");
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    let alive = true;
    void fetchClipOptions()
      .then((data) => alive && setOptions(data))
      .catch((err) => alive && setOptionsError(friendlyError(err)));
    return () => {
      alive = false;
    };
  }, []);

  function pickRange(id: string) {
    setRange(id);
    const found = RANGES.find((r) => r.id === id);
    if (found && id !== "custom") {
      setMinSeconds(found.min);
      setMaxSeconds(found.max);
    }
  }

  function addSegment(seed?: Partial<ManualSegment>) {
    setSegments((list) => [
      ...list,
      {
        uid: newUid(),
        start: seed?.start ?? "00:00",
        end: seed?.end ?? "01:00",
        title: seed?.title ?? "",
      },
    ]);
  }

  function patchSegment(uid: string, patch: Partial<ManualSegment>) {
    setManualError(null);
    setSegments((list) => list.map((seg) => (seg.uid === uid ? { ...seg, ...patch } : seg)));
  }

  function removeSegment(uid: string) {
    setSegments((list) => list.filter((seg) => seg.uid !== uid));
  }

  /** Manda o corte entregue de volta para a régua (ex.: refazer em 16:9). */
  function reeditClip(clip: ClipResult, nextAspect?: string) {
    setManualOn(true);
    if (nextAspect) setAspect(nextAspect);
    setSegments([
      {
        uid: newUid(),
        start: toTimecode(clip.start),
        end: toTimecode(clip.end),
        title: clip.title,
      },
    ]);
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    form.set("min_seconds", String(minSeconds));
    form.set("max_seconds", String(Math.max(minSeconds + 5, maxSeconds)));

    if (manualOn) {
      const parsed: { start: number; end: number; title: string }[] = [];
      for (const [index, seg] of segments.entries()) {
        const start = parseTimecode(seg.start);
        const end = parseTimecode(seg.end);
        if (start === null || end === null) {
          setManualError(`Tempo inválido no corte ${index + 1}. Use mm:ss ou hh:mm:ss.`);
          return;
        }
        if (end - start < 1) {
          setManualError(`O corte ${index + 1} precisa ter pelo menos 1 segundo.`);
          return;
        }
        parsed.push({ start, end, title: seg.title.trim() || `Corte manual ${index + 1}` });
      }
      if (!parsed.length) {
        setManualError("Adicione pelo menos um corte na régua ou desligue o modo manual.");
        return;
      }
      setManualError(null);
      form.set("segments", JSON.stringify(parsed));
    } else {
      form.delete("segments");
    }

    run(() => apiPostForm<Job>("/api/clips/run", form));
  }


  const clips = ((job?.meta as Record<string, unknown> | undefined)?.clips ??
    (job as unknown as { clips?: ClipResult[] })?.clips ??
    []) as ClipResult[];

  return (
    <ToolShell
      badge="Ferramenta 7 · /api/clips/run"
      title="Fábrica de Cortes Inteligentes"
      subtitle="Vídeo longo (upload ou link) entra, cortes verticais legendados saem. A IA ouve o vídeo inteiro, pontua gancho, emoção, dado concreto e payoff por nicho, e devolve quantos cortes bons o vídeo realmente aguenta — você só define a faixa de duração."
      left={
        <form ref={formRef} onSubmit={onSubmit} className="space-y-5">
          {optionsError ? (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              {optionsError}
            </p>
          ) : null}
          {options && !options.transcription ? (
            <p className="rounded-xl border border-warning/40 bg-warning/10 p-3 text-xs">
              {options.transcription_hint ??
                "Configure uma chave de transcrição na Central de APIs para ativar os cortes."}
            </p>
          ) : null}

          {card ? (
            <div className="rounded-xl border border-primary/40 bg-primary/5 p-3 text-xs">
              <p className="font-medium text-foreground">Vídeo da pesquisa selecionado</p>
              <p className="mt-1 truncate text-muted-foreground">{card.title}</p>
              <input type="hidden" name="url" value={card.url} />
              <input type="hidden" name="source_card" value={JSON.stringify(card)} />
              <button
                type="button"
                onClick={() => setCard(null)}
                className="mt-2 rounded-lg border border-border px-3 py-1 text-[11px] text-muted-foreground transition hover:text-foreground"
              >
                Remover seleção
              </button>
            </div>
          ) : null}

          <Field label="Vídeo longo" hint="MP4, MOV ou WEBM. Podcast, aula, live — qualquer duração.">
            {(id) => (
              <FileDrop
                id={id}
                name="video"
                accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
                hint="MP4 / MOV / WEBM / MKV"
                onSelect={(f) => setHasFile(Boolean(f))}
              />
            )}
          </Field>

          {!card ? (
            <Field label="Ou cole um link" hint="YouTube, TikTok e qualquer fonte suportada pelo yt-dlp.">
              {(id) => <TextInput id={id} name="url" placeholder="https://youtube.com/watch?v=…" />}
            </Field>
          ) : null}

          <Field label="Nicho do conteúdo" hint="Define quais gatilhos valem mais na hora de escolher os melhores momentos.">
            {(id) => (
              <SelectInput id={id} name="niche" defaultValue="auto">
                {(options?.niches ?? [{ id: "auto", label: "Detectar sozinho (universal)" }]).map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.emoji ? `${n.emoji} ` : ""}
                    {n.label}
                  </option>
                ))}
              </SelectInput>
            )}
          </Field>

          <Field label="Duração dos cortes" hint="O sistema decide sozinho quantos cortes o vídeo rende dentro dessa faixa.">
            {(id) => (
              <SelectInput id={id} value={range} onChange={(e) => pickRange(e.target.value)}>
                {RANGES.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </SelectInput>
            )}
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label={`Mínimo · ${secondsLabel(minSeconds)}`}>
              {(id) => (
                <TextInput
                  id={id}
                  type="number"
                  min={8}
                  max={1200}
                  value={minSeconds}
                  onChange={(e) => {
                    setRange("custom");
                    setMinSeconds(Number(e.target.value) || 8);
                  }}
                />
              )}
            </Field>
            <Field label={`Máximo · ${secondsLabel(maxSeconds)}`}>
              {(id) => (
                <TextInput
                  id={id}
                  type="number"
                  min={12}
                  max={1800}
                  value={maxSeconds}
                  onChange={(e) => {
                    setRange("custom");
                    setMaxSeconds(Number(e.target.value) || 12);
                  }}
                />
              )}
            </Field>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Formato de saída" hint="16:9 entrega corte horizontal pronto para YouTube.">
              {(id) => (
                <SelectInput
                  id={id}
                  name="aspect"
                  value={aspect}
                  onChange={(e) => setAspect(e.target.value)}
                >
                  <option value="9:16">9:16 — TikTok / Reels / Shorts</option>
                  <option value="1:1">1:1 — quadrado</option>
                  <option value="16:9">16:9 — horizontal (YouTube)</option>
                  <option value="original">Manter o original</option>
                </SelectInput>
              )}
            </Field>
            <Field label="Enquadramento">
              {(id) => (
                <SelectInput id={id} name="frame" value={frame} onChange={(e) => setFrame(e.target.value)}>
                  <option value="crop">Corte central (imagem cheia)</option>
                  <option value="blur">Vídeo inteiro com fundo desfocado</option>
                  <option value="pad">Vídeo inteiro com barras pretas</option>
                </SelectInput>
              )}
            </Field>
          </div>

          <div className="rounded-xl border border-border bg-background/40 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-foreground">Régua de edição manual</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {manualOn
                    ? "A IA não escolhe nada: entrega exatamente os trechos abaixo, no formato selecionado."
                    : "Ative para definir você mesmo o início e o fim de cada corte (mm:ss ou hh:mm:ss)."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setManualOn((v) => !v)}
                className={`rounded-lg border px-3 py-1.5 text-[11px] font-semibold transition ${
                  manualOn
                    ? "border-primary/60 bg-primary/10 text-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                {manualOn ? "Modo manual ligado" : "Ativar edição manual"}
              </button>
            </div>

            {manualOn ? (
              <div className="mt-3 space-y-3">
                {segments.map((seg, index) => (
                  <div key={seg.uid} className="rounded-lg border border-border/70 bg-card/40 p-2.5">
                    <div className="grid grid-cols-2 gap-2">
                      <TextInput
                        value={seg.start}
                        placeholder="00:00"
                        aria-label={`Início do corte ${index + 1}`}
                        onChange={(e) => patchSegment(seg.uid, { start: e.target.value })}
                      />
                      <TextInput
                        value={seg.end}
                        placeholder="01:30"
                        aria-label={`Fim do corte ${index + 1}`}
                        onChange={(e) => patchSegment(seg.uid, { end: e.target.value })}
                      />
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <TextInput
                        value={seg.title}
                        placeholder={`Corte manual ${index + 1}`}
                        aria-label={`Título do corte ${index + 1}`}
                        onChange={(e) => patchSegment(seg.uid, { title: e.target.value })}
                      />
                      <button
                        type="button"
                        onClick={() => removeSegment(seg.uid)}
                        className="shrink-0 rounded-lg border border-border px-2.5 py-1.5 text-[11px] text-muted-foreground transition hover:text-destructive"
                      >
                        Remover
                      </button>
                    </div>
                    <p className="mt-1.5 text-[11px] text-muted-foreground">
                      Duração: {segmentDurationLabel(seg)}
                    </p>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => addSegment()}
                  className="w-full rounded-lg border border-dashed border-border py-2 text-[11px] font-semibold text-muted-foreground transition hover:text-foreground"
                >
                  + Adicionar corte
                </button>
                {manualError ? (
                  <p className="text-[11px] text-destructive">{manualError}</p>
                ) : null}
                {options?.transcription === false && captionPreset !== "none" ? (
                  <p className="text-[11px] text-warning">
                    Sem chave de transcrição: escolha “Sem legenda” para rodar os cortes manuais mesmo assim.
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>


          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Estilo da legenda">
              {(id) => (
                <SelectInput id={id} name="caption_preset" defaultValue="hormozi" onChange={(e) => setCaptionPreset(e.target.value)}>
                  {(options?.presets ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                  <option value="none">Sem legenda</option>
                </SelectInput>
              )}
            </Field>
            <Field label="Posição da legenda">
              {(id) => (
                <SelectInput id={id} name="caption_position" defaultValue="bottom">
                  <option value="bottom">Embaixo</option>
                  <option value="center">Centro</option>
                  <option value="top">Em cima</option>
                </SelectInput>
              )}
            </Field>
          </div>

          <Field label="Música de fundo (opcional)" hint="Entra com ducking: abaixa sozinha quando a voz fala.">
            {(id) => (
              <FileDrop id={id} name="music" accept="audio/mpeg,audio/wav,audio/mp4,audio/aac" hint="MP3 / WAV / M4A" />
            )}
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5">
            <Field label="Volume da trilha">
              {(id) => (
                <SelectInput id={id} name="music_volume" defaultValue="0.12">
                  <option value="0.06">Discreto</option>
                  <option value="0.12">Padrão</option>
                  <option value="0.22">Presente</option>
                </SelectInput>
              )}
            </Field>
            <Field label="Idioma do áudio" hint="Deixe em automático se não tiver certeza.">
              {(id) => (
                <SelectInput id={id} name="language" defaultValue="">
                  <option value="">Detectar automaticamente</option>
                  <option value="pt">Português</option>
                  <option value="en">Inglês</option>
                  <option value="es">Espanhol</option>
                  <option value="fr">Francês</option>
                  <option value="it">Italiano</option>
                  <option value="de">Alemão</option>
                </SelectInput>
              )}
            </Field>
          </div>

          <Field
            label="Curadoria por IA"
            hint={
              options?.ai_ready
                ? "A IA reordena os cortes e escreve o título de cada um."
                : "Sem chave de LLM na Central de APIs — o ranking heurístico continua funcionando."
            }
          >
            {(id) => (
              <SelectInput id={id} name="use_ai" defaultValue="1">
                <option value="1">Ligada (recomendado)</option>
                <option value="0">Desligada — só heurística</option>
              </SelectInput>
            )}
          </Field>

          <MutationSelect defaultValue="auto" label="Esterilização" hint="Cada corte sai com hash inédito." />

          <JobSettingsGuard
            busy={busy}
            disabled={(!hasFile && !card) || (options?.transcription === false && !manualOn)}
            label="Gerar cortes"
            busyLabel="Cortando…"
          />
        </form>
      }
      right={
        <div className="space-y-5">
          <StatusPanel
            job={job}
            error={error}
            busy={busy}
            emptyHint="Envie um vídeo longo para acompanhar transcrição, curadoria dos melhores momentos e a entrega de cada corte."
            onCancel={cancel}
            onDelete={remove}
          />

          {clips.length ? (
            <div className="space-y-3">
              <p className="text-sm font-semibold">
                {clips.length} corte(s) entregues
              </p>
              <ul className="space-y-3">
                {clips.map((clip) => (
                  <li key={clip.index} className="rounded-xl border border-border bg-background/40 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-foreground">{clip.title}</p>
                        <p className="mt-0.5 text-[11px] text-muted-foreground">
                          {secondsLabel(clip.start)} → {secondsLabel(clip.end)} · {secondsLabel(clip.seconds)}
                          {clip.ai_score ? ` · nota ${clip.ai_score}` : ""}
                        </p>
                        {clip.reasons?.length ? (
                          <p className="mt-1 text-[11px] text-muted-foreground">{clip.reasons.join(" · ")}</p>
                        ) : null}
                      </div>
                      <a
                        href={downloadUrl(clip.download_url)}
                        className="shrink-0 rounded-lg border border-primary/50 px-3 py-1.5 text-[11px] font-semibold text-foreground hover:bg-primary/10"
                        download
                      >
                        Baixar
                      </a>
                    </div>
                    <video
                      src={downloadUrl(clip.download_url)}
                      controls
                      preload="none"
                      className="mt-3 w-full rounded-lg border border-border/60 bg-black"
                    />
                    <div className="mt-2 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => reeditClip(clip)}
                        className="rounded-lg border border-border px-2.5 py-1 text-[11px] text-muted-foreground transition hover:text-foreground"
                      >
                        Editar tempos
                      </button>
                      <button
                        type="button"
                        onClick={() => reeditClip(clip, "16:9")}
                        className="rounded-lg border border-border px-2.5 py-1 text-[11px] text-muted-foreground transition hover:text-foreground"
                      >
                        Refazer em 16:9
                      </button>
                    </div>

                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      }
      below={
        <div className="space-y-6">
          <DiscoveryPanel
            defaultPlatform="auto"
            actionLabel="Cortar este vídeo"
            onAction={setCard}
            actionBusyUrl={busy ? (card?.url ?? null) : null}
          />
          <ToolHistory
            tool="clips"
            title="Histórico · Fábrica de Cortes"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
