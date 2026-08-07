import { useEffect, useState } from "react";
import { Field, SelectInput, TextArea, TextInput } from "@/components/form";
import { apiDelete, apiGet, apiPostJson, downloadUrl, friendlyError, type Job } from "@/lib/api";
import { useJobRunner } from "@/hooks/use-job-runner";

export type Persona = {
  id: string;
  name: string;
  base_voice: string;
  pitch: number;
  formant: number;
  warmth: number;
  brightness: number;
  breath: number;
  body: number;
  room: number;
  tempo: number;
  rate: number;
  notes?: string;
  engine?: string;
  type?: string;
};


type BaseVoice = { id: string; name: string; labels?: string };
type PersonasResponse = {
  forge_ready: boolean;
  personas: Persona[];
  base_voices: BaseVoice[];
};

const BLANK: Persona = {
  id: "",
  name: "",
  base_voice: "pt-BR-AntonioNeural",
  pitch: -1.5,
  formant: 0.95,
  warmth: 2,
  brightness: 1.5,
  breath: 0.15,
  body: 0,
  room: 0.12,
  tempo: 1,
  rate: 0,
  notes: "",
  engine: "edge",
  type: "custom",
};


const SLIDERS: Array<{
  key: keyof Persona;
  label: string;
  min: number;
  max: number;
  step: number;
  hint: string;
}> = [
  { key: "pitch", label: "Altura (semitons)", min: -8, max: 8, step: 0.25, hint: "Grave ← → agudo" },
  { key: "formant", label: "Tamanho do trato vocal", min: 0.8, max: 1.25, step: 0.01, hint: "Corpo grande ← → corpo pequeno" },
  { key: "warmth", label: "Calor (graves)", min: -8, max: 8, step: 0.5, hint: "Peito e presença em 180 Hz" },
  { key: "body", label: "Corpo / nasalidade", min: -6, max: 6, step: 0.5, hint: "Região de 900 Hz" },
  { key: "brightness", label: "Brilho (agudos)", min: -8, max: 8, step: 0.5, hint: "Definição em 7 kHz" },
  { key: "breath", label: "Sopro / proximidade", min: 0, max: 1, step: 0.05, hint: "Sensação de microfone perto" },
  { key: "room", label: "Ambiência", min: 0, max: 1, step: 0.05, hint: "Sala natural ao redor da voz" },
  { key: "tempo", label: "Ritmo", min: 0.85, max: 1.15, step: 0.01, hint: "Velocidade da fala" },
];

export function VoiceForgePanel({ onChanged }: { onChanged?: (personas: Persona[]) => void }) {
  const [data, setData] = useState<PersonasResponse | null>(null);
  const [draft, setDraft] = useState<Persona>(BLANK);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState("");
  const [busy, setBusy] = useState<"" | "preview" | "save" | "variants" | "bulk" | "clone">("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [variants, setVariants] = useState<Persona[]>([]);
  const [variantCount, setVariantCount] = useState(6);
  const [variantIntensity, setVariantIntensity] = useState(0.6);
  const [variantAudio, setVariantAudio] = useState<Record<string, string>>({});
  const [variantBusy, setVariantBusy] = useState<string>("");
  const [cloneFile, setCloneFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const { job, run, cancel, remove: removeJob } = useJobRunner("voice:clone");

  const removeVariant = (id: string) => {
    setVariants(prev => prev.filter(v => v.id !== id));
  };



  async function load() {
    try {
      const res = await apiGet<PersonasResponse>("/api/voice/personas");
      setData(res);
      onChanged?.(res.personas);
    } catch (err) {
      setError(friendlyError(err));
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function set<K extends keyof Persona>(key: K, value: Persona[K]) {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }

  async function preview() {
    setBusy("preview");
    setError(null);
    setNotice(null);
    try {
      const res = await apiPostJson<{ url: string }>("/api/voice/personas/preview", {
        ...draft,
        id: draft.id || "forge_preview",
        name: draft.name || "Prévia",
        text: previewText.trim() || undefined,
      });
      setPreviewUrl(`${downloadUrl(res.url)}?t=${Date.now()}`);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy("");
    }
  }

  async function save() {
    if (!draft.name.trim()) {
      setError("Dê um nome para a voz antes de salvar.");
      return;
    }
    setBusy("save");
    setError(null);
    try {
      const res = await apiPostJson<{ persona: Persona }>("/api/voice/personas", draft);
      setDraft(res.persona);
      setNotice(`Voz “${res.persona.name}” salva no catálogo.`);
      await load();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy("");
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await apiDelete(`/api/voice/personas/${id}`);
      if (draft.id === id) setDraft(BLANK);
      await load();
    } catch (err) {
      setError(friendlyError(err));
    }
  }

  async function makeVariants() {
    setBusy("variants");
    setError(null);
    setNotice(null);
    try {
      const res = await apiPostJson<{ variants: Persona[] }>("/api/voice/personas/variants", {
        base: { ...draft, id: draft.id || "forge_base", name: draft.name || "Voz base" },
        count: variantCount,
        intensity: variantIntensity,
        seed: `${draft.name || draft.base_voice}:${variantCount}:${variantIntensity}`,
      });
      setVariants(res.variants);
      setVariantAudio({});
      setNotice(`${res.variants.length} modelos gerados. Ouça e salve os que curtir.`);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy("");
    }
  }

  async function previewVariant(variant: Persona) {
    setVariantBusy(variant.id);
    setError(null);
    try {
      const res = await apiPostJson<{ url: string }>("/api/voice/personas/preview", {
        ...variant,
        text: previewText.trim() || undefined,
      });
      setVariantAudio((prev) => ({ ...prev, [variant.id]: `${downloadUrl(res.url)}?t=${Date.now()}` }));
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setVariantBusy("");
    }
  }

  async function saveVariants(list: Persona[]) {
    setBusy("bulk");
    setError(null);
    try {
      const res = await apiPostJson<{ personas: Persona[] }>("/api/voice/personas/bulk", {
        personas: list,
      });
      setNotice(`${res.personas.length} voz(es) salva(s) no catálogo.`);
      await load();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy("");
    }
  }

  async function clone() {
    if (!cloneFile) {
      setError("Selecione um arquivo de áudio para clonar.");
      return;
    }
    if (!consent) {
      setError("Você precisa confirmar a autorização de uso da voz.");
      return;
    }
    
    setError(null);
    setNotice(null);
    
    await run(async () => {
      const form = new FormData();
      form.append("media", cloneFile);
      form.append("name", draft.name || cloneFile.name);
      form.append("consent", "true");
      return apiPostJson<Job>("/api/voice/personas/clone", form);
    });
    
    setCloneFile(null);
    setConsent(false);
  }

  // Monitorar conclusão do job de clonagem para atualizar a lista
  useEffect(() => {
    if (job?.status === "done") {
      setNotice("Clonagem neural concluída com sucesso!");
      void load();
    } else if (job?.status === "error") {
      setError(job.message || "Falha na clonagem neural.");
    }
  }, [job?.status, job?.message]);

  const baseVoices = data?.base_voices ?? [];


  return (
    <section className="rounded-2xl border border-border bg-card/60 p-5">
      <header className="mb-4">
        <h2 className="text-sm font-semibold text-foreground">🧬 Estúdio de Clonagem Neural</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Crie personas exclusivas via assinatura acústica ou extraia identidades vocais reais via Clonagem Neural (1-10 min).

        </p>
      </header>

      {data && !data.forge_ready ? (
        <p className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          Motor gratuito ausente no servidor. Rode <code>.venv/bin/pip install edge-tts</code> e reinicie o
          serviço <code>viral-api</code> para liberar a criação de vozes.
        </p>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="space-y-4">
          <div className="rounded-xl border border-primary/40 bg-primary/5 p-4 shadow-inner shadow-primary/5">
            <h3 className="text-xs font-bold text-foreground mb-3 flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/20 text-xs text-primary animate-pulse">
                🧬
              </span>
              Motor Neural Profissional (ElevenLabs)
            </h3>
            <div className="space-y-3">
              {!data?.forge_ready && (
                <p className="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-[10px] text-red-200">
                  Atenção: A ElevenLabs (Neural Real) requer chave API ativa em /apis. Se não configurada, o motor neural real não iniciará.
                </p>
              )}

              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="flex-1">
                  <input
                    type="file"
                    accept="audio/*,video/*"
                    onChange={(e) => {
                      const file = e.target.files?.[0] || null;
                      setCloneFile(file);
                      if (file && !draft.name) {
                        // Sugere o nome do arquivo como nome da voz
                        set("name", file.name.split('.')[0]);
                      }
                    }}
                    className="w-full text-xs text-muted-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-primary/20 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-primary hover:file:bg-primary/30"
                  />
                  <p className="mt-1 text-[10px] text-muted-foreground">Recomendado: 1-10 minutos de áudio limpo.</p>
                </div>
                <button
                  type="button"
                  onClick={() => void clone()}
                  disabled={!!job && job.status === "running" || !cloneFile || !consent}
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50"
                >
                  {job?.status === "running" ? "Processando DNA..." : "Clonar Voz (Neural Real)"}
                </button>
              </div>

              <label className="flex items-start gap-2 cursor-pointer group">
                <input 
                  type="checkbox" 
                  checked={consent}
                  onChange={(e) => setConsent(e.target.checked)}
                  className="mt-0.5 rounded border-primary/30 bg-primary/10 text-primary focus:ring-primary/50" 
                />
                <span className="text-[10px] text-muted-foreground leading-tight group-hover:text-foreground transition-colors">
                  Confirmo que tenho autorização legal e que este é um áudio real para clonagem neural definitiva.
                </span>
              </label>

              {job && (
                <div className="mt-2 space-y-1.5">
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-primary font-medium">{job.stage || "Processando..."}</span>
                    <span className="text-muted-foreground">{job.progress}%</span>
                  </div>
                  <div className="h-1 w-full overflow-hidden rounded-full bg-primary/10">
                    <div 
                      className="h-full bg-primary transition-all duration-500" 
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                  {job.status === "running" && (
                    <button 
                      onClick={() => void cancel()}
                      className="text-[9px] text-destructive hover:underline"
                    >
                      Cancelar processo
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-background/40 p-4 space-y-4">
            <h3 className="text-xs font-semibold text-foreground">Configurações da Voz / Metadados</h3>

            <Field label="Nome da voz">
              {(id) => (
                <TextInput
                  id={id}
                  value={draft.name}
                  placeholder="Ex.: Narrador do canal"
                  onChange={(e) => set("name", e.target.value)}
                />
              )}
            </Field>
            <Field label="Voz base (matéria-prima)">
              {(id) => (
                <SelectInput
                  id={id}
                  value={draft.base_voice}
                  onChange={(e) => set("base_voice", e.target.value)}
                >
                  {baseVoices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name}
                      {v.labels ? ` — ${v.labels}` : ""}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
          </div>

          <div className="rounded-xl border border-border bg-background/40 p-4 space-y-4">
            <h3 className="text-xs font-semibold text-foreground">Configurações Manuais / Ajuste de Persona</h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {SLIDERS.map((slider) => (
              <label key={String(slider.key)} className="block text-xs">
                <span className="flex items-center justify-between text-muted-foreground">
                  <span>{slider.label}</span>
                  <span className="font-mono text-foreground">
                    {Number(draft[slider.key] as number).toFixed(2)}
                  </span>
                </span>
                <input
                  type="range"
                  min={slider.min}
                  max={slider.max}
                  step={slider.step}
                  value={Number(draft[slider.key] as number)}
                  onChange={(e) => set(slider.key, Number(e.target.value) as never)}
                  className="mt-2 w-full accent-primary"
                />
                <span className="text-[11px] text-muted-foreground/70">{slider.hint}</span>
              </label>
            ))}
          </div>

          <Field label="Frase de teste" hint="Deixe vazio para usar a frase padrão de demonstração.">
            {(id) => (
              <TextArea
                id={id}
                value={previewText}
                rows={2}
                maxLength={400}
                placeholder="Escreva uma frase para ouvir a voz…"
                onChange={(e) => setPreviewText(e.target.value)}
              />
            )}
            </Field>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void preview()}
              disabled={busy !== "" || !(data?.forge_ready ?? false)}
              className="rounded-xl border border-border bg-background/60 px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:border-primary disabled:opacity-50"
            >
              {busy === "preview" ? "Gerando prévia…" : "Ouvir prévia"}
            </button>
            <button
              type="button"
              onClick={() => void save()}
              disabled={busy !== ""}
              className="rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {busy === "save"
                ? "Salvando…"
                : draft.id
                  ? "Salvar alterações"
                  : "Salvar voz no catálogo"}
            </button>

            {draft.id ? (
              <button
                type="button"
                onClick={() => setDraft(BLANK)}
                className="rounded-xl px-3 py-2 text-xs text-muted-foreground hover:text-foreground"
              >
                Nova voz
              </button>
            ) : null}
          </div>

          {previewUrl ? <audio controls src={previewUrl} className="w-full" /> : null}

          {draft.engine !== "elevenlabs" && (
            <div className="rounded-xl border border-border bg-background/40 p-4">
              <h3 className="text-xs font-semibold text-foreground">
                Fábrica de modelos · varie a mesma voz
              </h3>
              <p className="mt-1 text-[11px] text-muted-foreground">
                Gera vários modelos (grave, jovem, locutor, íntimo, cinematográfico…) a partir da voz
                acima. Ouça cada um e salve só os que servirem para o canal.
              </p>

              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label className="block text-xs">
                  <span className="flex items-center justify-between text-muted-foreground">
                    <span>Quantidade de modelos</span>
                    <span className="font-mono text-foreground">{variantCount}</span>
                  </span>
                  <input
                    type="range"
                    min={2}
                    max={16}
                    step={1}
                    value={variantCount}
                    onChange={(e) => setVariantCount(Number(e.target.value))}
                    className="mt-2 w-full accent-primary"
                  />
                </label>
                <label className="block text-xs">
                  <span className="flex items-center justify-between text-muted-foreground">
                    <span>Intensidade da variação</span>
                    <span className="font-mono text-foreground">{variantIntensity.toFixed(2)}</span>
                  </span>
                  <input
                    type="range"
                    min={0.05}
                    max={1.5}
                    step={0.05}
                    value={variantIntensity}
                    onChange={(e) => setVariantIntensity(Number(e.target.value))}
                    className="mt-2 w-full accent-primary"
                  />
                </label>
              </div>

              <div className="mt-3 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => void makeVariants()}
                  disabled={busy !== ""}
                  className="rounded-xl border border-border bg-background/60 px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:border-primary disabled:opacity-50"
                >
                  {busy === "variants" ? "Gerando modelos…" : "Gerar modelos"}
                </button>
                {variants.length ? (
                  <button
                    type="button"
                    onClick={() => void saveVariants(variants)}
                    disabled={busy !== ""}
                    className="rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
                  >
                    {busy === "bulk" ? "Salvando…" : `Salvar os ${variants.length} modelos`}
                  </button>
                ) : null}
              </div>

              {variants.length ? (
                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {variants.map((variant) => (
                    <div key={variant.id} className="rounded-xl border border-border bg-card/50 p-3">
                      <p className="text-xs font-semibold text-foreground">{variant.name}</p>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        {variant.base_voice} · pitch {Number(variant.pitch).toFixed(1)} · form{" "}
                        {Number(variant.formant).toFixed(2)} · ar {Number(variant.breath).toFixed(2)}
                      </p>
                      <div className="mt-2 flex gap-2">
                        <button
                          type="button"
                          onClick={() => void previewVariant(variant)}
                          disabled={variantBusy !== "" || !(data?.forge_ready ?? false)}
                          className="rounded-lg border border-border px-2 py-1 text-[11px] text-foreground hover:border-primary disabled:opacity-50"
                        >
                          {variantBusy === variant.id ? "Gerando…" : "Ouvir"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void saveVariants([variant])}
                          disabled={busy !== ""}
                          className="rounded-lg border border-border px-2 py-1 text-[11px] text-foreground hover:border-primary disabled:opacity-50"
                        >
                          Salvar
                        </button>
                        <button
                          type="button"
                          onClick={() => setDraft({ ...BLANK, ...variant, id: "" })}
                          className="rounded-lg px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground"
                        >
                          Editar
                        </button>
                      </div>
                      {variantAudio[variant.id] ? (
                        <audio controls src={variantAudio[variant.id]} className="mt-2 w-full" />
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )}


          {error ? (
            <p className="rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive-foreground">
              {error}
            </p>
          ) : null}
          {notice ? <p className="text-xs text-emerald-400">{notice}</p> : null}
        </div>

        <aside className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Vozes do catálogo
          </h3>
          {(data?.personas ?? []).map((persona) => (
            <div
              key={persona.id}
              className={`rounded-xl border px-3 py-2 text-xs ${
                draft.id === persona.id ? "border-primary bg-primary/10" : "border-border bg-background/40"
              }`}
            >
              <button
                type="button"
                onClick={() => setDraft({ ...BLANK, ...persona })}
                className="block w-full text-left font-semibold text-foreground"
              >
                {persona.name}
              </button>
              <p className="mt-1 text-[11px] text-muted-foreground">{persona.notes || persona.base_voice}</p>
              <button
                type="button"
                onClick={() => void remove(persona.id)}
                className="mt-2 text-[11px] text-destructive hover:underline"
              >
                Remover
              </button>
            </div>
          ))}
          {(data?.personas ?? []).length === 0 ? (
            <p className="text-xs text-muted-foreground">Nenhuma voz criada ainda.</p>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
