import { CheckCircle2, Loader2, Lock, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Trava de segurança antes de iniciar um job.
 *
 * O usuário precisa clicar em "Salvar configurações" para revisar, num resumo
 * legível, exatamente o que será enviado ao servidor. Só depois disso o botão
 * de iniciar libera. Qualquer alteração posterior invalida o snapshot e exige
 * salvar de novo — assim nenhum job caro roda com o preset errado.
 */

type Entry = { name: string; label: string; value: string };

/** Nomes amigáveis para campos ocultos (que não têm <label>). */
const FRIENDLY: Record<string, string> = {
  engine: "Motor de voz",
  voice_id: "Voz realista",
  persona_id: "Voz própria (persona)",
  target_voice: "Voz do motor local",
  mutation: "Esterilização",
  format: "Formato do áudio",
  keep_video: "Saída",
  keep_ambience: "Áudio original ao fundo",
  preserve_timing: "Preservar timing",
  target_lang: "Idioma da dublagem",
  url: "Link de origem",
  media: "Arquivo enviado",
  file: "Arquivo enviado",
  text: "Roteiro",
  speed: "Velocidade",
  style: "Expressividade",
};

const IGNORE = new Set(["", "csrf", "_token"]);

function labelFor(form: HTMLFormElement, el: HTMLElement, name: string): string {
  if (el.id) {
    const tag = form.querySelector<HTMLLabelElement>(`label[for="${CSS.escape(el.id)}"]`);
    const text = tag?.textContent?.trim();
    if (text) return text;
  }
  return FRIENDLY[name] ?? name;
}

const ENGINE_LABEL: Record<string, string> = {
  forge: "Voz própria (Voice Forge)",
  elevenlabs: "Voz realista (ElevenLabs)",
  local: "Motor local (DSP)",
};

/** Só um dos campos de voz importa — depende do motor escolhido. */
const VOICE_FIELD_OF_ENGINE: Record<string, string> = {
  forge: "persona_id",
  elevenlabs: "voice_id",
  local: "target_voice",
};

function humanize(value: string): string {
  return value
    .replace(/^forge_/, "")
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());
}

function readForm(form: HTMLFormElement): Entry[] {
  const out: Entry[] = [];
  const seen = new Set<string>();



  for (const el of Array.from(form.elements)) {
    const field = el as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
    const name = field.name ?? "";
    if (!name || IGNORE.has(name) || field.disabled) continue;
    if (field instanceof HTMLInputElement && (field.type === "submit" || field.type === "button")) {
      continue;
    }

    let value = "";
    if (field instanceof HTMLSelectElement) {
      value = field.selectedOptions[0]?.textContent?.trim() ?? field.value;
    } else if (field instanceof HTMLInputElement && field.type === "file") {
      const file = field.files?.[0];
      value = file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB` : "";
    } else if (field instanceof HTMLInputElement && field.type === "checkbox") {
      value = field.checked ? "sim" : "não";
    } else if (field instanceof HTMLInputElement && field.type === "radio") {
      if (!field.checked) continue;
      value = field.value;
    } else {
      value = field.value?.trim() ?? "";
    }

    if (!value) continue;
    if (seen.has(name)) continue;
    seen.add(name);

    if (value.length > 140) value = `${value.slice(0, 140)}…`;
    out.push({ name, label: labelFor(form, field, name), value });
  }

  return out;
}

type Props = {
  busy: boolean;
  /** Bloqueio externo (arquivo/link ausente, chave faltando…). */
  disabled?: boolean;
  /** Texto do botão que inicia o job. */
  label: string;
  /** Texto enquanto o job roda. */
  busyLabel: string;
  variant?: "primary" | "electric";
};

export function JobSettingsGuard({
  busy,
  disabled = false,
  label,
  busyLabel,
  variant = "primary",
}: Props) {
  const anchor = useRef<HTMLDivElement>(null);
  const [saved, setSaved] = useState<Entry[] | null>(null);
  const [stale, setStale] = useState(false);

  const form = () => anchor.current?.closest("form") ?? null;

  const save = useCallback(() => {
    const el = form();
    if (!el) return;
    setSaved(readForm(el));
    setStale(false);
  }, []);

  // Qualquer mudança depois de salvar invalida a revisão.
  useEffect(() => {
    const el = anchor.current?.closest("form");
    if (!el) return;
    const invalidate = () => setStale(true);
    el.addEventListener("input", invalidate);
    el.addEventListener("change", invalidate);
    return () => {
      el.removeEventListener("input", invalidate);
      el.removeEventListener("change", invalidate);
    };
  }, []);

  // Ao terminar um job, exige revisar de novo antes do próximo.
  useEffect(() => {
    if (busy) setStale(true);
  }, [busy]);

  const locked = !saved || stale;

  return (
    <div ref={anchor} className="space-y-3">
      <div className="rounded-xl border border-border bg-background/40 p-3 sm:p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2">
            {locked ? (
              <ShieldAlert className="mt-0.5 size-4 shrink-0 text-amber-400" aria-hidden="true" />
            ) : (
              <CheckCircle2
                className="mt-0.5 size-4 shrink-0 text-emerald-400"
                aria-hidden="true"
              />
            )}
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">
                {locked ? "Revise antes de iniciar" : "Configurações confirmadas"}
              </p>
              <p className="text-xs text-muted-foreground">
                {saved && stale
                  ? "Você mudou algo depois de salvar. Salve de novo para liberar o início."
                  : locked
                    ? "Salve as configurações para conferir o que será enviado ao servidor."
                    : "Pode iniciar — é exatamente isso que vai para o processamento."}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={save}
            disabled={busy}
            className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-xl border border-border bg-secondary px-4 py-2 text-sm font-semibold text-secondary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Lock className="size-4" aria-hidden="true" />
            {saved && !stale ? "Configurações salvas" : "Salvar configurações"}
          </button>
        </div>

        {saved && saved.length > 0 ? (
          <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1.5 border-t border-border pt-3 text-xs sm:grid-cols-2">
            {saved.map((entry) => (
              <div key={entry.name} className="flex min-w-0 items-baseline justify-between gap-3">
                <dt className="shrink-0 text-muted-foreground">{entry.label}</dt>
                <dd className="min-w-0 truncate text-right font-medium text-foreground">
                  {entry.value}
                </dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>

      <button
        type="submit"
        disabled={busy || disabled || locked}
        title={locked ? "Salve as configurações antes de iniciar" : undefined}
        className={`inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-center text-sm font-semibold transition-opacity disabled:cursor-not-allowed disabled:opacity-60 ${
          variant === "electric"
            ? "bg-electric text-electric-foreground hover:opacity-90"
            : "text-primary-foreground hover:opacity-90"
        }`}
        style={variant === "primary" ? { backgroundImage: "var(--gradient-viral)" } : undefined}
      >
        {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null}
        {busy ? busyLabel : locked ? "Salve as configurações para iniciar" : label}
      </button>
    </div>
  );
}
