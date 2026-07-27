import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  CheckCircle2,
  CircleAlert,
  CircleHelp,
  ExternalLink,
  KeyRound,
  Loader2,
  DownloadCloud,
  RefreshCw,

  Save,
  Trash2,
} from "lucide-react";

import { TopNav } from "@/components/TopNav";
import { apiGet, friendlyError, API_BASE } from "@/lib/api";

export const Route = createFileRoute("/apis")({
  head: () => ({
    meta: [
      { title: "Central de APIs — chaves e integrações do Ecossistema Viral" },
      {
        name: "description",
        content:
          "Gerencie, substitua e teste todas as chaves de API usadas no pipeline: LLMs, pesquisa web, extração, transcrição e TikTok.",
      },
      { property: "og:title", content: "Central de APIs — Ecossistema Viral" },
      {
        property: "og:description",
        content: "Troca e teste de chaves de API em um painel único e organizado.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ApisPage,
});

type TestResult = {
  ok: boolean | null;
  status: number;
  message: string;
  latency_ms?: number;
  at?: string;
};

type Provider = {
  id: string;
  name: string;
  category: string;
  env: string;
  docs: string;
  usage: string;
  prefix?: string | null;
  format_hint?: string | null;
  format_ok?: boolean | null;
  testable: boolean;

  configured: boolean;
  source: "cofre" | "env" | "vazio";
  masked: string;
  note: string;
  updated_at?: string | null;
  last_test?: TestResult | null;
};

async function apiSend<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error(data?.error ?? `Falha na requisição (HTTP ${res.status}).`);
  return data as T;
}

type ScanReport = {
  roots: string[];
  files_scanned: number;
  files: string[];
  env_vars_seen: number;
  hits: { id: string; name: string; found: boolean; var?: string | null; origin?: string }[];
};

function ApisPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testingAll, setTestingAll] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importReport, setImportReport] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("todas");
  const [scanning, setScanning] = useState(false);
  const [scan, setScan] = useState<ScanReport | null>(null);




  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ providers: Provider[] }>("/api/apis");
      setProviders(data.providers ?? []);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const categories = useMemo(
    () => ["todas", ...Array.from(new Set(providers.map((p) => p.category)))],
    [providers],
  );

  const visible = useMemo(
    () => providers.filter((p) => filter === "todas" || p.category === filter),
    [providers, filter],
  );

  const configured = providers.filter((p) => p.configured).length;
  const failing = providers.filter((p) => p.last_test?.ok === false).length;

  function replace(next: Provider) {
    setProviders((list) => list.map((p) => (p.id === next.id ? next : p)));
  }

  async function testAll() {
    setTestingAll(true);
    setError(null);
    try {
      const data = await apiSend<{ providers: Provider[] }>("/api/apis/test-all", "POST");
      setProviders(data.providers ?? []);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setTestingAll(false);
    }
  }

  async function importKeys(force: boolean) {
    setImporting(true);
    setError(null);
    setImportReport(null);
    try {
      const data = await apiSend<{
        providers: Provider[];
        report: {
          imported: string[];
          skipped: string[];
          scanned: number;
          roots?: string[];
          env_file?: string | null;
        };
      }>("/api/apis/import", "POST", { force });
      setProviders(data.providers ?? []);
      const n = data.report?.imported?.length ?? 0;
      const envInfo = data.report?.env_file ? ` Espelhadas com permissão 600 em ${data.report.env_file}.` : "";
      setImportReport(
        n > 0
          ? `${n} chave(s) importada(s) automaticamente: ${data.report.imported.join(", ")}.${envInfo}`
          : `Nenhuma chave encontrada. Foram lidos ${data.report?.scanned ?? 0} arquivo(s) em: ${(data.report?.roots ?? []).join(", ")}. Use "Diagnóstico" para ver os detalhes.`,
      );

    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setImporting(false);
    }
  }

  async function runScan() {
    setScanning(true);
    setError(null);
    try {
      const data = await apiGet<{ report: ScanReport }>("/api/apis/scan");
      setScan(data.report);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setScanning(false);
    }
  }




  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto max-w-7xl px-4 py-8 md:px-8">
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-medium text-foreground">
              <KeyRound className="size-3.5" aria-hidden="true" />
              Cofre · /api/apis
            </span>
            <h1 className="mt-3 text-3xl font-bold md:text-4xl">Central de APIs</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Todas as integrações do pipeline em um só lugar. Substitua uma chave que estourou o
              limite, remova a que não usa mais e teste a conectividade sem sair do painel — as
              chaves ficam no servidor, nunca no navegador.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-2.5 text-sm font-medium transition-colors hover:border-primary/50"
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              Recarregar
            </button>
            <button
              type="button"
              onClick={() => void importKeys(false)}
              disabled={importing}
              title="Varre .env, o app antigo e configs legadas do servidor e preenche as chaves sozinho"
              className="inline-flex items-center gap-2 rounded-xl border border-accent/50 bg-accent/10 px-4 py-2.5 text-sm font-semibold text-foreground transition-colors hover:border-accent disabled:opacity-60"
            >
              {importing ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <DownloadCloud className="size-4" aria-hidden="true" />
              )}
              Preencher automaticamente
            </button>
            <button
              type="button"
              onClick={() => void runScan()}
              disabled={scanning}
              title="Mostra onde o servidor procurou as chaves e o que encontrou"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-2.5 text-sm font-medium transition-colors hover:border-primary/50 disabled:opacity-60"
            >
              {scanning ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Activity className="size-4" aria-hidden="true" />
              )}
              Diagnóstico
            </button>


            <button
              type="button"
              onClick={() => void testAll()}
              disabled={testingAll}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
            >
              {testingAll ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Activity className="size-4" aria-hidden="true" />
              )}
              Testar todas
            </button>
          </div>
        </div>

        {importReport ? (
          <p className="mb-4 rounded-xl border border-accent/40 bg-accent/10 px-4 py-3 text-sm text-foreground">
            {importReport}
          </p>
        ) : null}

        {scan ? (
          <section className="panel mb-6 p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="font-display text-base font-semibold">Diagnóstico da varredura</h2>
              <button
                type="button"
                onClick={() => setScan(null)}
                className="rounded-full border border-border bg-surface/60 px-3 py-1 text-xs"
              >
                Fechar
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              {scan.files_scanned} arquivo(s) lidos · {scan.env_vars_seen} variáveis de ambiente ·
              diretórios: <span className="font-mono">{scan.roots.join(", ")}</span>
            </p>
            <ul className="mt-3 grid gap-1 text-xs sm:grid-cols-2">
              {scan.hits.map((hit) => (
                <li
                  key={hit.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background/40 px-3 py-1.5"
                >
                  <span>{hit.name}</span>
                  <span className={hit.found ? "text-success" : "text-muted-foreground"}>
                    {hit.found ? `achou · ${hit.var}` : "não encontrada"}
                  </span>
                </li>
              ))}
            </ul>
            {scan.files.length ? (
              <details className="mt-3">
                <summary className="cursor-pointer text-xs text-muted-foreground">
                  Ver arquivos varridos ({scan.files.length})
                </summary>
                <ul className="mt-2 max-h-56 space-y-0.5 overflow-auto font-mono text-[11px] text-muted-foreground">
                  {scan.files.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </section>
        ) : null}




        <dl className="mb-6 grid gap-3 sm:grid-cols-3">
          <Stat label="Integrações mapeadas" value={String(providers.length)} />
          <Stat label="Com chave ativa" value={`${configured}/${providers.length}`} />
          <Stat label="Com falha no último teste" value={String(failing)} tone={failing ? "bad" : "good"} />
        </dl>

        {error ? (
          <p className="mb-6 flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm">
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
            {error}
          </p>
        ) : null}

        <nav aria-label="Filtrar por categoria" className="mb-6 -mx-1 overflow-x-auto pb-1">
          <ul className="flex min-w-max gap-2 px-1">
            {categories.map((cat) => (
              <li key={cat}>
                <button
                  type="button"
                  onClick={() => setFilter(cat)}
                  className={
                    cat === filter
                      ? "rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                      : "rounded-full border border-border/80 bg-surface/70 px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
                  }
                >
                  {cat}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {loading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Carregando integrações…
          </p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {visible.map((provider) => (
              <ProviderCard key={provider.id} provider={provider} onChange={replace} />
            ))}
          </div>
        )}
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-10 text-xs text-muted-foreground md:px-8">
        Chaves gravadas em{" "}
        <code className="font-mono">fabrica_clips/_config/api_keys.json</code> (permissão 600, fora
        do Git). Variáveis de ambiente continuam valendo como fallback.
      </footer>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  return (
    <div className="panel px-4 py-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={`mt-1 text-2xl font-bold ${
          tone === "bad" ? "text-destructive" : tone === "good" ? "text-success" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

function ProviderCard({
  provider,
  onChange,
}: {
  provider: Provider;
  onChange: (p: Provider) => void;
}) {
  const [value, setValue] = useState("");
  const [note, setNote] = useState(provider.note ?? "");
  const [busy, setBusy] = useState<"save" | "test" | "delete" | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  async function save() {
    setBusy("save");
    setFeedback(null);
    setFailed(false);
    try {
      const data = await apiSend<{ provider: Provider }>(`/api/apis/${provider.id}`, "PUT", {
        key: value,
        note,
      });
      onChange(data.provider);
      setValue("");
      setFeedback("Chave atualizada.");
    } catch (err) {
      setFailed(true);
      setFeedback(friendlyError(err));
    } finally {
      setBusy(null);
    }
  }

  async function test() {
    setBusy("test");
    setFeedback(null);
    setFailed(false);
    try {
      const data = await apiSend<{ provider: Provider; result: TestResult }>(
        `/api/apis/${provider.id}/test`,
        "POST",
      );
      onChange(data.provider);
      setFailed(data.result.ok === false);
      setFeedback(data.result.message);
    } catch (err) {
      setFailed(true);
      setFeedback(friendlyError(err));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("delete");
    setFeedback(null);
    setFailed(false);
    try {
      const data = await apiSend<{ provider: Provider }>(`/api/apis/${provider.id}`, "DELETE");
      onChange(data.provider);
      setFeedback("Chave removida do cofre.");
    } catch (err) {
      setFailed(true);
      setFeedback(friendlyError(err));
    } finally {
      setBusy(null);
    }
  }

  const last = provider.last_test;
  const inputId = `key-${provider.id}`;

  return (
    <article className="panel flex flex-col gap-4 p-5">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{provider.name}</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">{provider.category}</p>
        </div>
        <HealthPill provider={provider} />
      </header>

      <p className="text-sm text-muted-foreground">{provider.usage}</p>

      <dl className="grid gap-2 text-xs">
        <Row label="Chave atual" value={provider.masked || "não configurada"} mono />
        <Row label="Variável" value={provider.env} mono />
        <Row
          label="Origem"
          value={
            provider.source === "cofre"
              ? "Cofre do painel"
              : provider.source === "env"
                ? "Variável de ambiente"
                : "—"
          }
        />
        {provider.updated_at ? <Row label="Atualizada em" value={provider.updated_at} /> : null}
        {last ? (
          <Row
            label="Último teste"
            value={`${last.message}${last.latency_ms ? ` · ${last.latency_ms} ms` : ""}`}
          />
        ) : null}
      </dl>

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
          className="w-full rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm outline-none focus:border-primary"
        />
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Anotação (ex.: conta de produção, plano pago)"
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void save()}
            disabled={!value.trim() || busy !== null}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
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
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium transition-colors hover:border-primary/50 disabled:opacity-50"
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
            className="inline-flex items-center gap-2 rounded-lg border border-destructive/40 px-3 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-40"
          >
            <Trash2 className="size-4" aria-hidden="true" />
            Remover
          </button>
          <a
            href={provider.docs}
            target="_blank"
            rel="noreferrer noopener"
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Docs
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
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/50 px-3 py-2">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className={`truncate text-right ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

function HealthPill({ provider }: { provider: Provider }) {
  const ok = provider.last_test?.ok;
  if (!provider.configured) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
        <CircleHelp className="size-3" aria-hidden="true" />
        Sem chave
      </span>
    );
  }
  if (ok === true) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-success/50 bg-success/15 px-3 py-1 text-xs">
        <CheckCircle2 className="size-3 text-success" aria-hidden="true" />
        Operacional
      </span>
    );
  }
  if (ok === false) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-destructive/50 bg-destructive/15 px-3 py-1 text-xs">
        <CircleAlert className="size-3 text-destructive" aria-hidden="true" />
        Falhando
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-electric/50 bg-electric/10 px-3 py-1 text-xs">
      <KeyRound className="size-3" aria-hidden="true" />
      Configurada
    </span>
  );
}
