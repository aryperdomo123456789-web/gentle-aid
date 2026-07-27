import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import {
  Beaker,
  CircleAlert,
  CircleCheck,
  ClipboardCopy,
  Loader2,
  Play,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";

import { TopNav } from "@/components/TopNav";
import { probeApi } from "@/lib/api-lab.functions";
import { LAB_GROUPS, LAB_PRESETS, findPreset } from "@/lib/api-lab.presets";
import type { LabResult } from "@/lib/api-lab.server";

export const Route = createFileRoute("/lab")({
  head: () => ({
    meta: [
      { title: "Laboratório de APIs - teste real de respostas | Ecossistema Viral" },
      {
        name: "description",
        content:
          "Ferramenta isolada para disparar chamadas reais a Groq, Whisper, ElevenLabs, Gemini e outros, ver a resposta bruta e anotar o contrato antes de plugar no pipeline.",
      },
      { property: "og:title", content: "Laboratório de APIs - Ecossistema Viral" },
      {
        property: "og:description",
        content: "Dispare chamadas reais, veja a resposta crua e só depois encaixe a API no backend.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LabPage,
});

type Note = {
  id: string;
  at: string;
  preset: string;
  status: number;
  verdict: string;
  ms: number;
};

function pretty(text: string, contentType: string): string {
  if (!text) return "(corpo vazio)";
  if (contentType.includes("json") || text.trimStart().startsWith("{") || text.trimStart().startsWith("[")) {
    try {
      return JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      return text;
    }
  }
  return text;
}

function LabPage() {
  const run = useServerFn(probeApi);

  const [presetId, setPresetId] = useState(LAB_PRESETS[0].id);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [values, setValues] = useState<Record<string, Record<string, string>>>({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<LabResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);

  const preset = useMemo(() => findPreset(presetId)!, [presetId]);
  const presetValues = values[presetId] ?? {};

  function fieldValue(name: string, fallback?: string) {
    return presetValues[name] ?? fallback ?? "";
  }

  function setField(name: string, value: string) {
    setValues((prev) => ({ ...prev, [presetId]: { ...(prev[presetId] ?? {}), [name]: value } }));
  }

  async function execute() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const payload: Record<string, string> = {};
      for (const field of preset.fields ?? []) {
        payload[field.name] = fieldValue(field.name, field.defaultValue);
      }
      const data = await run({
        data: { presetId, key: keys[presetId] ?? "", values: payload },
      });
      setResult(data);
      setNotes((prev) => [
        {
          id: `${Date.now()}`,
          at: new Date().toLocaleTimeString("pt-BR"),
          preset: preset.label,
          status: data.status,
          verdict: data.verdict,
          ms: data.durationMs,
        },
        ...prev,
      ].slice(0, 30));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha inesperada ao executar a chamada.");
    } finally {
      setBusy(false);
    }
  }

  const body = result ? pretty(result.bodyPreview, result.contentType) : "";

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-[1600px] px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <header className="mb-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-xs font-medium text-foreground">
            <Beaker className="size-3.5" aria-hidden="true" />
            Bancada isolada · roda aqui, não depende do aaPanel
          </span>
          <h1 className="mt-3 text-2xl font-bold leading-tight sm:text-3xl md:text-4xl">
            Laboratório de APIs
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Dispare a chamada <strong>real</strong> de cada provedor, veja o corpo cru que ele
            devolve e só então encaixe no backend. A requisição sai do servidor desta preview (sem
            CORS) e a chave é usada uma única vez — nada é gravado.
          </p>
        </header>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          {/* ------------------------------------------------ Painel esquerdo */}
          <section className="panel space-y-4 p-4 sm:p-5">
            <div>
              <label htmlFor="preset" className="text-xs font-medium text-muted-foreground">
                Chamada
              </label>
              <select
                id="preset"
                value={presetId}
                onChange={(e) => {
                  setPresetId(e.target.value);
                  setResult(null);
                  setError(null);
                }}
                className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
              >
                {LAB_GROUPS.map((group) => (
                  <optgroup key={group} label={group}>
                    {LAB_PRESETS.filter((p) => p.group === group).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>

            <p className="rounded-xl border border-border/70 bg-surface/60 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
              {preset.expects}
            </p>

            <div>
              <label htmlFor="key" className="text-xs font-medium text-muted-foreground">
                {preset.keyLabel}
              </label>
              <input
                id="key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                placeholder={preset.keyHint ?? "cole a chave aqui"}
                value={keys[presetId] ?? ""}
                onChange={(e) => setKeys((prev) => ({ ...prev, [presetId]: e.target.value }))}
                className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 font-mono text-sm"
              />
              {preset.docs ? (
                <a
                  href={preset.docs}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-xs text-primary underline"
                >
                  onde gerar essa chave
                </a>
              ) : null}
            </div>

            {(preset.fields ?? []).map((field) => (
              <div key={field.name}>
                <label
                  htmlFor={`f-${field.name}`}
                  className="text-xs font-medium text-muted-foreground"
                >
                  {field.label}
                </label>
                {field.multiline ? (
                  <textarea
                    id={`f-${field.name}`}
                    rows={3}
                    value={fieldValue(field.name, field.defaultValue)}
                    onChange={(e) => setField(field.name, e.target.value)}
                    className="mt-1 w-full rounded-xl border border-border bg-background px-3 py-2 font-mono text-xs"
                  />
                ) : (
                  <input
                    id={`f-${field.name}`}
                    value={fieldValue(field.name, field.defaultValue)}
                    placeholder={field.placeholder}
                    onChange={(e) => setField(field.name, e.target.value)}
                    className="mt-1 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2 font-mono text-sm"
                  />
                )}
              </div>
            ))}

            <button
              type="button"
              onClick={() => void execute()}
              disabled={busy}
              className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
            >
              {busy ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Play className="size-4" aria-hidden="true" />
              )}
              Disparar chamada real
            </button>

            {notes.length > 0 ? (
              <div className="pt-2">
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Caderno de anotações
                  </h2>
                  <button
                    type="button"
                    onClick={() => setNotes([])}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="size-3.5" aria-hidden="true" />
                    limpar
                  </button>
                </div>
                <ul className="space-y-1.5">
                  {notes.map((note) => (
                    <li
                      key={note.id}
                      className="rounded-lg border border-border/70 bg-surface/50 px-3 py-2 text-xs"
                    >
                      <span className="font-mono text-muted-foreground">{note.at}</span>{" "}
                      <span className="font-semibold">{note.preset}</span>
                      <span
                        className={
                          note.status >= 200 && note.status < 300
                            ? " text-success"
                            : " text-destructive"
                        }
                      >
                        {" "}
                        · HTTP {note.status} · {note.ms} ms
                      </span>
                      <p className="mt-1 text-muted-foreground">{note.verdict}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>

          {/* ------------------------------------------------- Painel direito */}
          <section className="space-y-4">
            {error ? (
              <p className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm">
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                {error}
              </p>
            ) : null}

            {!result && !error ? (
              <div className="panel p-6 text-sm text-muted-foreground">
                <p className="font-medium text-foreground">Nenhuma chamada executada ainda.</p>
                <p className="mt-2">
                  Escolha um preset, cole a chave e dispare. O painel mostra status, cabeçalhos e o
                  corpo exatamente como o provedor devolve — é esse contrato que deve ser copiado
                  para o backend no aaPanel.
                </p>
              </div>
            ) : null}

            {result ? (
              <>
                <div
                  className={`panel flex flex-wrap items-center gap-3 p-4 ${
                    result.ok ? "border-success/40" : "border-destructive/40"
                  }`}
                >
                  {result.ok ? (
                    <CircleCheck className="size-5 shrink-0 text-success" aria-hidden="true" />
                  ) : (
                    <CircleAlert className="size-5 shrink-0 text-destructive" aria-hidden="true" />
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-semibold">
                      HTTP {result.status} {result.statusText} · {result.durationMs} ms ·{" "}
                      {result.bodyBytes} bytes
                    </p>
                    <p className="text-xs text-muted-foreground">{result.verdict}</p>
                  </div>
                </div>

                <div className="panel p-4 text-xs">
                  <p className="font-mono break-all">
                    <span className="font-semibold">{result.method}</span> {result.url}
                  </p>
                  <p className="mt-1 text-muted-foreground">
                    Headers enviados: {result.requestHeaders.join(", ") || "(nenhum)"}
                  </p>
                  <details className="mt-2">
                    <summary className="cursor-pointer text-muted-foreground">
                      Headers da resposta
                    </summary>
                    <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-all font-mono text-[11px] text-muted-foreground">
                      {Object.entries(result.responseHeaders)
                        .map(([k, v]) => `${k}: ${v}`)
                        .join("\n") || "(nenhum)"}
                    </pre>
                  </details>
                </div>

                <div className="panel p-4">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold">Resposta bruta</h2>
                    <button
                      type="button"
                      onClick={() => void navigator.clipboard.writeText(body)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs hover:border-primary/50"
                    >
                      <ClipboardCopy className="size-3.5" aria-hidden="true" />
                      Copiar
                    </button>
                  </div>
                  <pre className="max-h-[540px] overflow-auto whitespace-pre-wrap break-all rounded-xl bg-background/70 p-3 font-mono text-[12px] leading-relaxed">
                    {body}
                  </pre>
                  {result.truncated ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Resposta truncada em 20.000 caracteres.
                    </p>
                  ) : null}
                </div>
              </>
            ) : null}
          </section>
        </div>
      </main>
    </div>
  );
}
