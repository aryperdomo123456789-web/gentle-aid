import { Activity, ExternalLink, Loader2, Save, Trash2 } from "lucide-react";
import { useState } from "react";

import { friendlyError } from "@/lib/http";
import { deleteProviderKey, saveProviderKey, testProvider } from "../api";
import type { Provider } from "../types";
import { HealthPill } from "./HealthPill";

type BusyAction = "save" | "test" | "delete" | null;

const SOURCE_LABEL: Record<Provider["source"], string> = {
  cofre: "Cofre do painel",
  env: "Variável de ambiente",
  vazio: "—",
};

/** Card de uma integração: troca de chave, teste de conectividade e remoção. */
export function ProviderCard({
  provider,
  onChange,
}: {
  provider: Provider;
  onChange: (provider: Provider) => void;
}) {
  const [value, setValue] = useState("");
  const [note, setNote] = useState(provider.note ?? "");
  const [busy, setBusy] = useState<BusyAction>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  async function perform(action: Exclude<BusyAction, null>, task: () => Promise<string>) {
    setBusy(action);
    setFeedback(null);
    setFailed(false);
    try {
      setFeedback(await task());
    } catch (err) {
      setFailed(true);
      setFeedback(friendlyError(err));
    } finally {
      setBusy(null);
    }
  }

  const save = () =>
    perform("save", async () => {
      onChange(await saveProviderKey(provider.id, { key: value, note }));
      setValue("");
      return "Chave atualizada.";
    });

  const test = () =>
    perform("test", async () => {
      const data = await testProvider(provider.id);
      onChange(data.provider);
      setFailed(data.result.ok === false);
      return data.result.message;
    });

  const remove = () =>
    perform("delete", async () => {
      onChange(await deleteProviderKey(provider.id));
      return "Chave removida do cofre.";
    });

  const last = provider.last_test;
  const inputId = `key-${provider.id}`;

  return (
    <article className="panel flex min-w-0 flex-col gap-4 p-4 sm:p-5">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
        <div className="min-w-0">
          <h2 className="break-words text-base font-semibold">{provider.name}</h2>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <p className="text-xs text-muted-foreground">{provider.category}</p>
            <span
              className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                provider.project_active
                  ? "border-success/40 bg-success/10 text-success"
                  : "border-border bg-surface/60 text-muted-foreground"
              }`}
            >
              {provider.project_label}
            </span>
          </div>
        </div>
        <HealthPill provider={provider} />
      </header>

      <p className="text-sm text-muted-foreground">{provider.usage}</p>

      <dl className="grid gap-2 text-xs">
        <Row label="Chave atual" value={provider.masked || "não configurada"} mono />
        <Row label="Variável" value={provider.env} mono />
        <Row label="Origem" value={SOURCE_LABEL[provider.source]} />
        {provider.updated_at ? <Row label="Atualizada em" value={provider.updated_at} /> : null}
        {last ? (
          <Row
            label="Último teste"
            value={`${last.message}${last.latency_ms ? ` · ${last.latency_ms} ms` : ""}`}
          />
        ) : null}
      </dl>

      {provider.format_ok === false ? (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          Formato incompatível: esta chave deveria começar com{" "}
          <code className="font-mono">{provider.prefix}</code>. Substitua por uma credencial válida.
        </p>
      ) : null}
      {last?.remediation ? (
        <p className="rounded-lg border border-electric/40 bg-electric/10 px-3 py-2 text-xs text-electric">
          <span className="font-semibold">Como resolver: </span>
          {last.remediation}
        </p>
      ) : null}
      {provider.format_hint ? (
        <p className="text-xs text-muted-foreground">{provider.format_hint}</p>
      ) : null}

      <div className="space-y-3 rounded-xl border border-border bg-background/40 p-3">
        <label htmlFor={inputId} className="block text-xs font-medium text-muted-foreground">
          Nova chave {provider.prefix ? `(começa com ${provider.prefix})` : ""}
        </label>
        <input
          id={inputId}
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Cole aqui a chave de substituição"
          className="w-full min-h-11 rounded-lg border border-border bg-background px-3 py-2 font-mono text-base outline-none focus:border-primary sm:text-sm"
        />
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Anotação (ex.: conta de produção, plano pago)"
          className="w-full min-h-11 rounded-lg border border-border bg-background px-3 py-2 text-base outline-none focus:border-primary sm:text-sm"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void save()}
            disabled={!value.trim() || busy !== null}
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold sm:flex-none text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {busy === "save" ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Save className="size-4" aria-hidden="true" />
            )}
            Salvar
          </button>
          <button
            type="button"
            onClick={() => void test()}
            disabled={busy !== null || !provider.configured}
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium sm:flex-none transition-colors hover:border-primary/50 disabled:opacity-50"
          >
            {busy === "test" ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Activity className="size-4" aria-hidden="true" />
            )}
            Testar
          </button>
          <button
            type="button"
            onClick={() => void remove()}
            disabled={busy !== null || provider.source !== "cofre"}
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg border border-destructive/40 px-3 py-2 text-sm font-medium sm:flex-none text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-40"
          >
            <Trash2 className="size-4" aria-hidden="true" />
            Remover
          </button>
          <a
            href={provider.docs}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex min-h-11 items-center gap-1.5 text-sm sm:ml-auto text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Documentação
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
        </div>

        {feedback ? (
          <p className={`text-xs ${failed ? "text-destructive" : "text-success"}`}>{feedback}</p>
        ) : null}
      </div>
    </article>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-background/50 px-3 py-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className={`min-w-0 break-all sm:truncate sm:text-right ${mono ? "font-mono" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
