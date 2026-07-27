import { useMemo, useState } from "react";

import { apiPostJson, downloadUrl, friendlyError } from "@/lib/api";
import type { Persona } from "@/components/VoiceForgePanel";

export type Engine = "elevenlabs" | "forge" | "local";
export type RealisticVoice = { id: string; name: string; labels?: string };
export type LocalVoice = { id: string; name: string };

export const TEST_SCRIPT = `Testando a voz deste canal, do começo ao fim, sem cortes.

Presta atenção no que vou te contar agora, porque isso muda completamente a forma como você enxerga o próximo vídeo que aparecer na sua tela. Em dois mil e vinte e quatro, mais de setenta por cento do conteúdo que viralizou não tinha nada de especial na imagem: o que segurava a pessoa era a voz. O tom, a pausa, a respiração no lugar certo.

Repara na diferença: uma frase curta prende. Uma frase longa, bem construída, com vírgulas no lugar certo, conduz a pessoa por dentro da história até ela esquecer que está assistindo a um vídeo de trinta segundos.

E tem os detalhes técnicos: números como 3, 17, 250 mil e 1,8 milhão; siglas como IA, CPU, TikTok e YouTube; perguntas — você faria isso? — e exclamações. Tudo isso precisa sair limpo, natural, sem parecer robô.

Se você chegou até aqui e a voz continuou agradável, sem chiado e sem cansar o ouvido, é essa a voz do canal. Salva ela e vamos pro próximo.`;

const LOCAL_FALLBACK: LocalVoice[] = [
  { id: "masc_grave", name: "Masculino grave" },
  { id: "masc_jovem", name: "Masculino jovem" },
  { id: "fem_suave", name: "Feminino suave" },
  { id: "fem_energetica", name: "Feminino energética" },
  { id: "narrador", name: "Narrador documentário" },
];

export type VoiceSelection = {
  engine: Engine;
  voiceId: string;
  personaId: string;
  targetVoice: string;
};

type Props = {
  value: VoiceSelection;
  onChange: (next: VoiceSelection) => void;
  realisticVoices: RealisticVoice[];
  personas: Persona[];
  localVoices?: LocalVoice[];
  elevenReady: boolean;
  forgeReady: boolean;
  /** Mostra o motor local (só faz sentido em troca de narrador de mídia). */
  allowLocal?: boolean;
  testScript?: string;
  /** Dispara a recriação das vozes de fábrica no backend. */
  onSyncPersonas?: () => Promise<void>;
};

export function VoicePicker({
  value,
  onChange,
  realisticVoices,
  personas,
  localVoices,
  elevenReady,
  forgeReady,
  allowLocal = true,
  testScript,
  onSyncPersonas,
}: Props) {
  const [query, setQuery] = useState("");
  const [script, setScript] = useState(testScript || TEST_SCRIPT);
  const [audio, setAudio] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openScript, setOpenScript] = useState(false);

  const engines = useMemo(
    () =>
      (
        [
          ["elevenlabs", "Realista (ElevenLabs)", elevenReady],
          ["forge", "Minhas vozes (grátis)", forgeReady],
          ...(allowLocal ? ([["local", "Timbre local", true]] as const) : []),
        ] as Array<[Engine, string, boolean]>
      ).filter(Boolean),
    [elevenReady, forgeReady, allowLocal],
  );

  const options = useMemo(() => {
    const term = query.trim().toLowerCase();
    const list: Array<{ id: string; name: string; labels?: string }> =
      value.engine === "elevenlabs"
        ? realisticVoices
        : value.engine === "forge"
          ? personas.map((p) => ({ id: p.id, name: p.name, labels: p.base_voice }))
          : (localVoices?.length ? localVoices : LOCAL_FALLBACK);
    if (!term) return list;
    return list.filter((v) => `${v.name} ${v.labels ?? ""}`.toLowerCase().includes(term));
  }, [value.engine, query, realisticVoices, personas, localVoices]);

  const selectedId =
    value.engine === "elevenlabs"
      ? value.voiceId
      : value.engine === "forge"
        ? value.personaId
        : value.targetVoice;

  function pick(id: string) {
    setAudio(null);
    if (value.engine === "elevenlabs") onChange({ ...value, voiceId: id });
    else if (value.engine === "forge") onChange({ ...value, personaId: id });
    else onChange({ ...value, targetVoice: id });
  }

  function switchEngine(engine: Engine) {
    setAudio(null);
    setError(null);
    const next = { ...value, engine };
    if (engine === "elevenlabs" && !next.voiceId) next.voiceId = realisticVoices[0]?.id ?? "";
    if (engine === "forge" && !next.personaId) next.personaId = personas[0]?.id ?? "";
    if (engine === "local" && !next.targetVoice) next.targetVoice = LOCAL_FALLBACK[0].id;
    onChange(next);
  }

  async function test() {
    if (!selectedId) {
      setError("Escolha uma voz antes de testar.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await apiPostJson<{ url: string }>("/api/voice/preview", {
        engine: value.engine,
        voice_id: value.voiceId,
        persona_id: value.personaId,
        target_voice: value.targetVoice,
        text: script.trim() || TEST_SCRIPT,
      });
      setAudio(`${downloadUrl(res.url)}?t=${Date.now()}`);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-primary/30 bg-primary/5 p-4">
      <input type="hidden" name="engine" value={value.engine} />
      <input type="hidden" name="voice_id" value={value.voiceId} />
      <input type="hidden" name="persona_id" value={value.personaId} />
      <input type="hidden" name="target_voice" value={value.targetVoice} />

      <header className="mb-3">
        <h3 className="text-sm font-semibold text-foreground">Escolha a voz do narrador</h3>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Selecione, ouça o roteiro de teste e siga. A voz escolhida aqui é a que será usada no
          processamento abaixo.
        </p>
      </header>

      <div className="scroll-x flex gap-2 overflow-x-auto rounded-xl border border-border bg-background/50 p-1 sm:flex-wrap sm:overflow-visible">
        {engines.map(([id, label, enabled]) => (
          <button
            key={id}
            type="button"
            disabled={!enabled}
            onClick={() => switchEngine(id)}
            className={`min-h-10 shrink-0 whitespace-nowrap rounded-lg px-3 py-2 text-[11px] sm:flex-1 font-semibold transition-colors disabled:opacity-40 ${
              value.engine === id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Buscar voz pelo nome…"
        className="mt-3 w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-xs text-foreground outline-none placeholder:text-muted-foreground focus:border-primary"
      />

      <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
        {options.length === 0 ? (
          <p className="rounded-xl border border-border bg-background/40 px-3 py-3 text-[11px] text-muted-foreground">
            {value.engine === "forge"
              ? "Nenhuma voz própria ainda. Vá em “Criar voz” e gere seus modelos."
              : "Nenhuma voz encontrada para essa busca."}
          </p>
        ) : (
          options.map((v) => {
            const active = v.id === selectedId;
            return (
              <button
                key={v.id}
                type="button"
                onClick={() => pick(v.id)}
                className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left transition-colors ${
                  active
                    ? "border-primary bg-primary/10"
                    : "border-border bg-background/40 hover:border-primary/60"
                }`}
              >
                <span className="min-w-0">
                  <span className="block truncate text-xs font-semibold text-foreground">{v.name}</span>
                  {v.labels ? (
                    <span className="block truncate font-mono text-[10px] text-muted-foreground">
                      {v.labels}
                    </span>
                  ) : null}
                </span>
                <span
                  className={`h-3 w-3 shrink-0 rounded-full border ${
                    active ? "border-primary bg-primary" : "border-border"
                  }`}
                />
              </button>
            );
          })
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void test()}
          disabled={busy || !selectedId}
          className="rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Gerando teste…" : "Ouvir o roteiro de teste"}
        </button>
        <button
          type="button"
          onClick={() => setOpenScript((v) => !v)}
          className="text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          {openScript ? "Ocultar roteiro de teste" : "Ver / editar roteiro de teste"}
        </button>
        {script !== TEST_SCRIPT ? (
          <button
            type="button"
            onClick={() => setScript(TEST_SCRIPT)}
            className="text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            Restaurar roteiro padrão
          </button>
        ) : null}
      </div>

      {openScript ? (
        <textarea
          value={script}
          onChange={(e) => setScript(e.target.value)}
          rows={8}
          className="mt-3 w-full rounded-xl border border-border bg-background/60 px-3 py-2 text-xs leading-relaxed text-foreground outline-none focus:border-primary"
        />
      ) : null}

      {audio ? <audio controls src={audio} className="mt-3 w-full" /> : null}
      {error ? (
        <p className="mt-3 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-[11px] text-destructive-foreground">
          {error}
        </p>
      ) : null}
    </section>
  );
}
