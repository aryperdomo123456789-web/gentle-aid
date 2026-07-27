import { Activity, CircleAlert, DownloadCloud, KeyRound, Loader2, RefreshCw, Wrench } from "lucide-react";
import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";

import { TopNav } from "@/components/TopNav";
import {
  fetchProviders,
  importKeys,
  scanKeys,
  testAllProviders,
  type ImportReport,
} from "@/features/apis/api";
import { ProviderCard } from "@/features/apis/components/ProviderCard";
import { ScanReportPanel } from "@/features/apis/components/ScanReportPanel";
import type { Provider, ScanReport } from "@/features/apis/types";
import { friendlyError } from "@/lib/http";

export const Route = createFileRoute("/apis")({
  head: () => ({
    meta: [
      { title: "Central de APIs - chaves e integrações do Ecossistema Viral" },
      {
        name: "description",
        content:
          "Gerencie, substitua e teste todas as chaves de API usadas no pipeline: LLMs, pesquisa web, extração, transcrição e TikTok.",
      },
      { property: "og:title", content: "Central de APIs - Ecossistema Viral" },
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

const ALL_CATEGORIES = "todas";

function describeImport(report: ImportReport | undefined): string {
  const imported = report?.imported ?? [];
  if (imported.length > 0) {
    const envInfo = report?.env_file
      ? ` Espelhadas com permissão 600 em ${report.env_file}.`
      : "";
    return `${imported.length} chave(s) importada(s) automaticamente: ${imported.join(", ")}.${envInfo}`;
  }
  return `Nenhuma chave encontrada. Foram lidos ${report?.scanned ?? 0} arquivo(s) em: ${(
    report?.roots ?? []
  ).join(", ")}. Use "Diagnóstico" para ver os detalhes.`;
}

function ApisPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testingAll, setTestingAll] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importReport, setImportReport] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>(ALL_CATEGORIES);
  const [scanning, setScanning] = useState(false);
  const [scan, setScan] = useState<ScanReport | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProviders(await fetchProviders());
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
    () => [ALL_CATEGORIES, ...Array.from(new Set(providers.map((p) => p.category)))],
    [providers],
  );

  const visible = useMemo(
    () => providers.filter((p) => filter === ALL_CATEGORIES || p.category === filter),
    [providers, filter],
  );

  const configured = providers.filter((p) => p.configured).length;
  const failing = providers.filter((p) => p.last_test?.ok === false).length;

  const replace = useCallback((next: Provider) => {
    setProviders((list) => list.map((p) => (p.id === next.id ? next : p)));
  }, []);

  async function testAll() {
    setTestingAll(true);
    setError(null);
    try {
      setProviders(await testAllProviders());
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setTestingAll(false);
    }
  }

  async function runImport(force: boolean, repair = false) {
    setImporting(true);
    setError(null);
    setImportReport(null);
    try {
      const data = await importKeys({ force, repair });
      setProviders(data.providers ?? []);
      setImportReport(describeImport(data.report));
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
      setScan(await scanKeys());
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-[1600px] px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-medium text-foreground">
              <KeyRound className="size-3.5" aria-hidden="true" />
              Cofre · /api/apis
            </span>
            <h1 className="mt-3 text-2xl font-bold leading-tight sm:text-3xl md:text-4xl">
              Central de APIs
            </h1>
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
              onClick={() => void runImport(false)}
              disabled={importing}
              title="Varre .env, o app antigo e configurações legadas do servidor e preenche as chaves sozinho"
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
              onClick={() => void runImport(false, true)}
              disabled={importing}
              title="Só nas integrações que falharam: procura outra chave do mesmo provedor no legado, testa de verdade e troca apenas se a nova funcionar"
              className="inline-flex items-center gap-2 rounded-xl border border-success/50 bg-success/10 px-4 py-2.5 text-sm font-semibold text-foreground transition-colors hover:border-success disabled:opacity-60"
            >
              {importing ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Wrench className="size-4" aria-hidden="true" />
              )}
              Reparar as que falharam
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

        {scan ? <ScanReportPanel report={scan} onClose={() => setScan(null)} /> : null}

        <dl className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat label="Integrações mapeadas" value={String(providers.length)} />
          <Stat label="Com chave ativa" value={`${configured}/${providers.length}`} />
          <Stat
            label="Com falha no último teste"
            value={String(failing)}
            tone={failing ? "bad" : "good"}
          />
        </dl>

        {error ? (
          <p className="mb-6 flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm">
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
            {error}
          </p>
        ) : null}

        <nav
          aria-label="Filtrar por categoria"
          className="scroll-x -mx-3 mb-6 overflow-x-auto pb-1 sm:-mx-1"
        >
          <ul className="flex min-w-max gap-2 px-3 sm:px-1">
            {categories.map((cat) => (
              <li key={cat}>
                <button
                  type="button"
                  onClick={() => setFilter(cat)}
                  className={
                    cat === filter
                      ? "min-h-10 whitespace-nowrap rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
                      : "min-h-10 whitespace-nowrap rounded-full border border-border/80 bg-surface/70 px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
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
        ) : providers.length === 0 ? (
          <div className="panel p-6 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">
              Nenhuma integração retornada pelo backend.
            </p>
            <p className="mt-2">
              O painel busca <code className="font-mono">/api/apis</code>. Se a resposta falhar, o
              serviço Flask (<code className="font-mono">viral-api</code>) está parado ou o Nginx
              não está encaminhando <code className="font-mono">/api</code> para o Gunicorn.
            </p>
            <button
              type="button"
              onClick={() => void load()}
              className="mt-4 inline-flex items-center gap-2 rounded-xl border border-primary/50 bg-primary/10 px-4 py-2.5 text-sm font-semibold transition-colors hover:border-primary"
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              Tentar de novo
            </button>
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {visible.map((provider) => (
              <ProviderCard key={provider.id} provider={provider} onChange={replace} />
            ))}
          </div>
        )}
      </main>
      <footer className="mx-auto w-full max-w-[1600px] px-3 pb-10 text-xs sm:px-4 text-muted-foreground md:px-8">
        Chaves gravadas em <code className="font-mono">fabrica_clips/_config/api_keys.json</code>{" "}
        (permissão 600, fora do Git). Variáveis de ambiente continuam valendo como fallback.
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
