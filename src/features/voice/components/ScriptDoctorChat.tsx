import { AlertTriangle, Check, Loader2, Sparkles, Undo2, Wand2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { SelectInput, TextArea } from "@/components/form";
import { analyzeScript, fixScript, fetchScriptStyles } from "@/features/voice/api";
import type { ScriptAnalysis, ScriptFixResult, ScriptStyle, ScriptAction } from "@/features/voice/types";
import { cn } from "@/lib/utils";

type Turn = {
  id: number;
  role: "user" | "ai";
  text: string;
  meta?: string;
  changes?: string[];
  script?: string;
};

type Props = {
  /** Texto atual do roteiro (o mesmo que vai para o TTS). */
  value: string;
  onChange: (next: string) => void;
  maxChars: number;
  /** Aplica velocidade/expressividade sugeridas pelo estilo escolhido. */
  onStyleHint?: (hint: { speed: string; style: number }) => void;
};

let turnId = 0;

/**
 * Chat de correção de roteiro.
 *
 * O usuário escolhe um estilo narrativo (terror, notícia, true crime…), manda a
 * IA corrigir/reescrever e só depois gera o áudio. Sem chave de IA cadastrada o
 * backend ainda devolve a correção local — por isso o painel nunca fica inútil.
 */
export function ScriptDoctorChat({ value, onChange, maxChars, onStyleHint }: Props) {
  const [styles, setStyles] = useState<ScriptStyle[]>([]);
  const [actions, setActions] = useState<ScriptAction[]>([]);
  const [aiReady, setAiReady] = useState(true);
  const [styleId, setStyleId] = useState("neutro");
  const [instruction, setInstruction] = useState("");
  const [seconds, setSeconds] = useState<string>("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<ScriptAnalysis | null>(null);
  const previous = useRef<string | null>(null);
  const feed = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    fetchScriptStyles()
      .then((data) => {
        if (!alive) return;
        setStyles(data.styles ?? []);
        setActions(data.actions ?? []);
        setAiReady(Boolean(data.ai_ready));
      })
      .catch(() => setAiReady(false));
    return () => {
      alive = false;
    };
  }, []);

  // Diagnóstico local com debounce: mostra os problemas antes de gastar IA.
  useEffect(() => {
    const text = value.trim();
    if (text.length < 20) {
      setAnalysis(null);
      return;
    }
    const timer = setTimeout(() => {
      analyzeScript(text)
        .then((res) => setAnalysis(res.analysis))
        .catch(() => undefined);
    }, 600);
    return () => clearTimeout(timer);
  }, [value]);

  useEffect(() => {
    feed.current?.scrollTo({ top: feed.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const style = useMemo(() => styles.find((s) => s.id === styleId), [styles, styleId]);

  function pickStyle(next: string) {
    setStyleId(next);
    const chosen = styles.find((s) => s.id === next);
    if (chosen && onStyleHint) {
      onStyleHint({ speed: chosen.velocidade, style: chosen.expressividade });
    }
  }

  async function runAction(action: string) {
    const text = value.trim();
    if (text.length < 10) {
      setError("Escreva pelo menos uma frase no roteiro antes de chamar a IA.");
      return;
    }
    setError(null);
    setBusy(action);
    const label = actions.find((a) => a.id === action)?.label ?? action;
    setTurns((prev) => [
      ...prev,
      {
        id: (turnId += 1),
        role: "user",
        text: instruction.trim() || `${label} · estilo ${style?.label ?? styleId}`,
      },
    ]);

    try {
      const result: ScriptFixResult = await fixScript({
        text,
        style: styleId,
        action,
        instruction: instruction.trim(),
        seconds: seconds ? Number(seconds) : undefined,
      });
      previous.current = value;
      onChange(result.script.slice(0, maxChars));
      setAnalysis(result.analysis);
      setInstruction("");
      setTurns((prev) => [
        ...prev,
        {
          id: (turnId += 1),
          role: "ai",
          text: result.note || "Roteiro atualizado.",
          changes: result.changes,
          script: result.script,
          meta: result.fallback
            ? "correção local (sem IA)"
            : `${result.provider ?? "ia"} · ${result.analysis.estimated_seconds}s de narração`,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao falar com a IA.");
    } finally {
      setBusy(null);
    }
  }

  function undo() {
    if (previous.current === null) return;
    onChange(previous.current);
    previous.current = null;
  }

  return (
    <div className="space-y-4 rounded-2xl border border-border/70 bg-muted/20 p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Sparkles className="size-4 shrink-0 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">Doutor de Roteiro</h3>
        <span className="text-xs text-muted-foreground">
          A IA corrige e reescreve no estilo antes de virar áudio
        </span>
      </div>

      {!aiReady ? (
        <p className="flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-2.5 text-xs text-amber-200">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
          Nenhuma chave de IA cadastrada. A correção local (pontuação, muletas, respiração) continua
          funcionando; cadastre DeepSeek, Groq, OpenRouter ou Mistral em /apis para liberar a
          reescrita por estilo.
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1.5 text-sm">
          <span className="block font-medium text-foreground">Estilo da narração</span>
          <SelectInput value={styleId} onChange={(e) => pickStyle(e.target.value)}>
            {styles.map((s) => (
              <option key={s.id} value={s.id}>
                {s.emoji} {s.label}
              </option>
            ))}
          </SelectInput>
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="block font-medium text-foreground">Duração alvo (segundos)</span>
          <input
            type="number"
            min={5}
            max={900}
            value={seconds}
            placeholder="opcional — ex.: 45"
            onChange={(e) => setSeconds(e.target.value)}
            className="min-h-11 w-full rounded-xl border border-input bg-background/60 px-3 py-2.5 text-base text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/40 sm:text-sm"
          />
        </label>
      </div>

      {style ? (
        <p className="text-xs text-muted-foreground">
          <strong className="text-foreground">{style.label}:</strong> {style.resumo} · ritmo {style.ritmo}
        </p>
      ) : null}

      {analysis ? (
        <div className="space-y-2 rounded-xl border border-border/60 bg-background/40 p-3">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>{analysis.words} palavras</span>
            <span>~{analysis.estimated_seconds}s de narração</span>
            <span>{analysis.avg_words_per_sentence} palavras/frase</span>
          </div>
          {analysis.problems.length ? (
            <ul className="space-y-1 text-xs text-amber-200">
              {analysis.problems.map((p) => (
                <li key={p} className="flex items-start gap-1.5">
                  <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                  <span>{p}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="flex items-center gap-1.5 text-xs text-emerald-300">
              <Check className="size-3.5" /> Roteiro pronto para narração.
            </p>
          )}
        </div>
      ) : null}

      {turns.length ? (
        <div ref={feed} className="max-h-64 space-y-2 overflow-y-auto pr-1">
          {turns.map((turn) => (
            <div
              key={turn.id}
              className={cn(
                "rounded-xl border p-2.5 text-xs",
                turn.role === "user"
                  ? "ml-6 border-primary/40 bg-primary/10 text-foreground"
                  : "mr-6 border-border/60 bg-background/60 text-muted-foreground",
              )}
            >
              <p className="text-foreground">{turn.text}</p>
              {turn.changes?.length ? (
                <ul className="mt-1.5 list-disc space-y-0.5 pl-4">
                  {turn.changes.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              ) : null}
              {turn.meta ? <p className="mt-1.5 text-[11px] opacity-70">{turn.meta}</p> : null}
            </div>
          ))}
        </div>
      ) : null}

      <TextArea
        rows={2}
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        placeholder="Peça algo específico à IA (opcional): 'deixa o final mais assustador', 'tira a parte do preço'…"
        className="min-h-16 font-sans"
      />

      <div className="flex flex-wrap gap-2">
        {actions.map((action) => (
          <button
            key={action.id}
            type="button"
            title={action.hint}
            disabled={busy !== null}
            onClick={() => runAction(action.id)}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border/70 bg-background/70 px-3 text-xs font-medium text-foreground transition hover:border-primary/60 hover:text-primary disabled:opacity-50"
          >
            {busy === action.id ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Wand2 className="size-3.5" />
            )}
            {action.label}
          </button>
        ))}
        {previous.current !== null ? (
          <button
            type="button"
            onClick={undo}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border/70 px-3 text-xs text-muted-foreground transition hover:text-foreground"
          >
            <Undo2 className="size-3.5" /> Desfazer
          </button>
        ) : null}
      </div>

      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
