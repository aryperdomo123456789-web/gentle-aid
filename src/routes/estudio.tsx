import { createFileRoute } from "@tanstack/react-router";
import { Loader2, Sparkles, Wand2 } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { Field, FileDrop, SelectInput, TextArea, TextInput } from "@/components/form";
import { JobSettingsGuard } from "@/components/JobSettingsGuard";
import { MutationSelect } from "@/components/MutationSelect";
import { StatusPanel } from "@/features/jobs/components/StatusPanel";
import { ToolHistory } from "@/features/jobs/components/ToolHistory";
import { ToolShell } from "@/components/ToolShell";
import { useJobRunner } from "@/hooks/use-job-runner";
import { apiGet, apiPostForm, apiPostJson, friendlyError, type Job } from "@/lib/api";

export const Route = createFileRoute("/estudio")({
  head: () => ({
    meta: [
      { title: "Estúdio de Vídeo IA — do prompt ao vídeo pronto" },
      {
        name: "description",
        content:
          "Gere vídeos completos com IA: roteiro em cenas, narração, imagem ou b-roll, legenda animada e esterilização — tudo no seu servidor.",
      },
      { property: "og:title", content: "Estúdio de Vídeo IA — Ecossistema Viral" },
      {
        property: "og:description",
        content:
          "Storyboard por IA, narração grátis, imagem Pollinations ou b-roll Pexels e legenda viral queimada no vídeo.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Estudio,
});

type Scene = { narration: string; visual: string; query: string; seconds?: number };
type Plan = {
  title: string;
  hook?: string;
  scenes: Scene[];
  provider?: string | null;
  fallback?: boolean;
  note?: string;
  total_seconds?: number;
};
type Options = {
  styles: { id: string; label: string; emoji?: string }[];
  looks: { id: string; label: string }[];
  modes: { id: string; label: string; free: boolean }[];
  aspects: string[];
  presets: { id: string; label: string }[];
  positions: string[];
  voices: { id: string; name: string }[];
  personas: { id: string; name: string }[];
  llm_ready: boolean;
  tts_ready: boolean;
};

const MODE_HINT: Record<string, string> = {
  ia: "Imagem gerada de graça (Pollinations) + zoom/pan cinematográfico no FFmpeg.",
  broll: "Vídeo real de banco gratuito por palavra-chave (Pexels, com Pixabay de reserva).",
  upload: "Suas imagens/clipes entram na ordem das cenas; a IA só narra, monta e legenda.",
  premium: "Slot para vídeo por IA pago — cadastre o provedor em /apis antes de usar.",
};

function Estudio() {
  const { job, error, busy, run, cancel, remove } = useJobRunner("studio");
  const formRef = useRef<HTMLFormElement>(null);

  const [options, setOptions] = useState<Options | null>(null);
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("neutro");
  const [sceneCount, setSceneCount] = useState(8);
  const [seconds, setSeconds] = useState(45);
  const [mode, setMode] = useState("ia");
  const [look, setLook] = useState("cartoon");
  const [aspect, setAspect] = useState("9:16");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  useMemo(() => {
    void (async () => {
      try {
        setOptions(await apiGet<Options>("/api/studio/options"));
      } catch {
        /* opções indisponíveis: a tela continua utilizável com os padrões */
      }
    })();
  }, []);

  async function buildStoryboard() {
    setPlanning(true);
    setPlanError(null);
    try {
      const data = await apiPostJson<Plan>("/api/studio/storyboard", {
        prompt,
        style,
        scenes: sceneCount,
        seconds,
      });
      setPlan(data);
      setScenes(data.scenes ?? []);
    } catch (err) {
      setPlanError(friendlyError(err));
    } finally {
      setPlanning(false);
    }
  }

  function patchScene(index: number, patch: Partial<Scene>) {
    setScenes((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  function start() {
    const el = formRef.current;
    if (!el) return;
    const form = new FormData(el);
    form.set("scenes", JSON.stringify(scenes));
    form.set("title", plan?.title ?? prompt.slice(0, 120));
    run(() => apiPostForm<Job>("/api/studio/run", form));
  }

  const modeLabel = options?.modes.find((m) => m.id === mode)?.label ?? mode;
  const entries = [
    { name: "title", label: "Título", value: plan?.title || prompt.slice(0, 60) || "—" },
    { name: "scenes", label: "Cenas", value: `${scenes.length}` },
    { name: "mode", label: "Fonte visual", value: modeLabel },
    { name: "aspect", label: "Formato", value: aspect },
    { name: "look", label: "Direção de arte", value: look },
    {
      name: "duration",
      label: "Duração estimada",
      value: `${Math.round(scenes.reduce((a, s) => a + (s.seconds ?? 4), 0))}s`,
    },
  ];
  const signature = JSON.stringify([scenes, mode, aspect, look]);

  return (
    <ToolShell
      badge="Ferramenta 6 · /api/studio/run"
      title="Estúdio de Vídeo IA"
      subtitle="Escreva a ideia: a IA quebra em cenas, narra com a sua voz, busca ou gera o visual de cada cena, queima a legenda viral e entrega o MP4 já esterilizado."
      left={
        <form
          ref={formRef}
          onSubmit={(e) => e.preventDefault()}
          className="space-y-5"
        >
          <Field label="Ideia do vídeo" hint="Quanto mais concreto, melhor o storyboard.">
            {(id) => (
              <TextArea
                id={id}
                rows={5}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Ex.: 3 curiosidades sobre o oceano profundo que ninguém acredita, tom de mistério, final com pergunta."
              />
            )}
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Estilo narrativo">
              {(id) => (
                <SelectInput id={id} value={style} onChange={(e) => setStyle(e.target.value)}>
                  {(options?.styles ?? [{ id: "neutro", label: "Neutro" }]).map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.emoji ? `${s.emoji} ` : ""}
                      {s.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field label="Duração alvo (s)">
              {(id) => (
                <TextInput
                  id={id}
                  type="number"
                  min={10}
                  max={600}
                  value={seconds}
                  onChange={(e) => setSeconds(Number(e.target.value))}
                />
              )}
            </Field>
            <Field label="Número de cenas">
              {(id) => (
                <TextInput
                  id={id}
                  type="number"
                  min={3}
                  max={24}
                  value={sceneCount}
                  onChange={(e) => setSceneCount(Number(e.target.value))}
                />
              )}
            </Field>
            <Field label="Formato">
              {(id) => (
                <SelectInput
                  id={id}
                  name="aspect"
                  value={aspect}
                  onChange={(e) => setAspect(e.target.value)}
                >
                  {(options?.aspects ?? ["9:16", "16:9", "1:1"]).map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
          </div>

          <button
            type="button"
            onClick={buildStoryboard}
            disabled={planning || prompt.trim().length < 8}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-border bg-secondary px-4 text-sm font-semibold text-secondary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {planning ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Wand2 className="size-4" aria-hidden="true" />
            )}
            {planning ? "Montando o storyboard…" : "Gerar storyboard com IA"}
          </button>

          {planError ? (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              {planError}
            </p>
          ) : null}
          {plan?.fallback ? (
            <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-300">
              {plan.note ?? "Storyboard local (sem IA). Cadastre a chave Groq em /apis — é grátis."}
            </p>
          ) : plan?.provider ? (
            <p className="text-xs text-muted-foreground">
              Storyboard escrito por <span className="font-medium text-foreground">{plan.provider}</span>.
            </p>
          ) : null}

          {scenes.length > 0 ? (
            <div className="space-y-3 rounded-xl border border-border bg-background/40 p-3">
              <p className="text-sm font-medium text-foreground">
                {scenes.length} cena(s) — edite antes de gerar
              </p>
              <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1">
                {scenes.map((scene, index) => (
                  <div key={index} className="rounded-lg border border-border/70 bg-surface/50 p-3">
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Cena {index + 1}
                    </p>
                    <TextArea
                      rows={2}
                      value={scene.narration}
                      onChange={(e) => patchScene(index, { narration: e.target.value })}
                      aria-label={`Narração da cena ${index + 1}`}
                    />
                    <TextInput
                      className="mt-2"
                      value={scene.visual}
                      onChange={(e) => patchScene(index, { visual: e.target.value })}
                      aria-label={`Visual da cena ${index + 1}`}
                      placeholder="Descrição visual (inglês)"
                    />
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Fonte visual" hint={MODE_HINT[mode]}>
              {(id) => (
                <SelectInput id={id} name="mode" value={mode} onChange={(e) => setMode(e.target.value)}>
                  {(options?.modes ?? [{ id: "ia", label: "Imagem IA grátis", free: true }]).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field label="Direção de arte">
              {(id) => (
                <SelectInput id={id} name="look" value={look} onChange={(e) => setLook(e.target.value)}>
                  {(options?.looks ?? [{ id: "cartoon", label: "Cartoon 3D" }]).map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field label="Voz da narração">
              {(id) => (
                <SelectInput id={id} name="voice" defaultValue="pt-BR-AntonioNeural">
                  {(options?.voices ?? []).map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field label="Voz própria (persona)" hint="Opcional — assinatura acústica do Voice Forge.">
              {(id) => (
                <SelectInput id={id} name="persona_id" defaultValue="">
                  <option value="">Sem persona</option>
                  {(options?.personas ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field label="Legenda">
              {(id) => (
                <SelectInput id={id} name="caption_preset" defaultValue="hormozi">
                  <option value="none">Sem legenda</option>
                  {(options?.presets ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <Field label="Posição da legenda">
              {(id) => (
                <SelectInput id={id} name="caption_position" defaultValue="bottom">
                  {(options?.positions ?? ["bottom", "center", "top"]).map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
          </div>

          {mode === "upload" ? (
            <Field label="Suas mídias" hint="Imagens ou clipes usados na ordem das cenas.">
              {(id) => (
                <FileDrop id={id} name="media" accept="image/*,video/mp4,video/webm" multiple hint="JPG / PNG / MP4" />
              )}
            </Field>
          ) : null}

          <Field label="Trilha sonora (opcional)" hint="Entra em ducking automático sob a narração.">
            {(id) => <FileDrop id={id} name="music" accept="audio/*" hint="MP3 / WAV / M4A" />}
          </Field>

          <MutationSelect defaultValue="media" label="Nível de esterilização" hint="" />

          {options && !options.tts_ready ? (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
              Motor de narração indisponível: instale <code>edge-tts</code> no servidor.
            </p>
          ) : null}

          <JobSettingsGuard
            busy={busy}
            disabled={scenes.length === 0}
            label="Gerar vídeo"
            busyLabel="Gerando cenas…"
            entries={entries}
            signature={signature}
            onStart={start}
          />
        </form>
      }
      right={
        <StatusPanel
          job={job}
          error={error}
          busy={busy}
          emptyHint="Gere o storyboard, revise as cenas e salve as configurações para iniciar."
          onCancel={cancel}
          onDelete={remove}
        />
      }
      below={
        <div className="space-y-6">
          <div className="rounded-xl border border-border bg-surface/40 p-4 text-xs text-muted-foreground">
            <p className="mb-1 flex items-center gap-2 font-medium text-foreground">
              <Sparkles className="size-4" aria-hidden="true" /> Custo real
            </p>
            Storyboard no Groq (grátis) com DeepSeek de reserva, narração Edge TTS (grátis) e visual
            Pollinations (grátis, sem chave). B-roll do Pexels/Pixabay usa chave gratuita cadastrada
            na Central de APIs.
          </div>
          <ToolHistory
            tool="studio"
            title="Histórico · Estúdio de Vídeo IA"
            refreshKey={`${job?.job_id ?? ""}-${job?.status ?? ""}`}
          />
        </div>
      }
    />
  );
}
