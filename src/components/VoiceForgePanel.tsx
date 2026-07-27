import { useEffect, useState } from "react";

import { Field, SelectInput, TextArea, TextInput } from "@/components/form";
import { apiDelete, apiGet, apiPostJson, downloadUrl, friendlyError } from "@/lib/api";

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
  const [busy, setBusy] = useState<"" | "preview" | "save">("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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

  const baseVoices = data?.base_voices ?? [];

  return (
    <section className="rounded-2xl border border-border bg-card/60 p-5">
      <header className="mb-4">
        <h2 className="text-sm font-semibold text-foreground">Voice Forge · crie a sua própria voz</h2>
        <p className="mt-1 text-xs text-muted-foreground">
          O motor gratuito gera a fala base e o Forge aplica uma assinatura acústica exclusiva por cima —
          altura, formantes, timbre, sopro e ambiência. O resultado não soa como a voz padrão de nenhum
          provedor e fica igual em todos os vídeos do canal.
        </p>
      </header>

      {data && !data.forge_ready ? (
        <p className="mb-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          Motor gratuito ausente no servidor. Rode <code>.venv/bin/pip install edge-tts</code> e reinicie o
          serviço <code>viral-api</code> para liberar a criação de vozes.
        </p>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[1fr_260px]">
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
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

          <div className="grid gap-4 sm:grid-cols-2">
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
