import {
  BadgeCheck,
  CalendarClock,
  Copy,
  KeyRound,
  Loader2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";

import { TopNav } from "@/components/TopNav";
import { useAuth } from "@/components/AuthProvider";
import { friendlyError } from "@/lib/http";
import { createReleaseKey, fetchReleaseKeys, revokeReleaseKey } from "@/features/access-keys/api";
import type { ReleaseKey } from "@/features/access-keys/types";

export const Route = createFileRoute("/api-hub/chaves")({
  head: () => ({
    meta: [
      { title: "Chaves de Acesso - API Mago Pro" },
      {
        name: "description",
        content:
          "Crie chaves de liberação com data de vencimento, revogue acessos e acompanhe o status das credenciais da API.",
      },
      { property: "og:title", content: "Chaves de Acesso - API Mago Pro" },
      { property: "og:type", content: "website" },
    ],
  }),
  component: AccessKeysPage,
});

function AccessKeysPage() {
  const auth = useAuth();
  const [keys, setKeys] = useState<ReleaseKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [label, setLabel] = useState("Gerador Mago");
  const [expiresDays, setExpiresDays] = useState("30");
  const [scopes, setScopes] = useState("api, public, saas");
  const [createdKey, setCreatedKey] = useState<ReleaseKey | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setKeys(await fetchReleaseKeys());
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!auth.ready || !auth.user || auth.user.role !== "owner") {
      setLoading(false);
      return;
    }
    void load();
  }, [auth.ready, auth.user, load]);

  const stats = useMemo(() => {
    const active = keys.filter((key) => key.status === "active");
    const expiringSoon = active.filter((key) => key.expires_in_days <= 7).length;
    return {
      total: keys.length,
      active: active.length,
      expiringSoon,
    };
  }, [keys]);

  async function handleCreate() {
    setCreating(true);
    setError(null);
    try {
      const next = await createReleaseKey({
        label,
        expires_in_days: Number.parseInt(expiresDays, 10),
        scopes: scopes
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setCreatedKey(next);
      setKeys((list) => [next, ...list]);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id: string) {
    setRevokingId(id);
    setError(null);
    try {
      const revoked = await revokeReleaseKey(id);
      setKeys((list) => list.map((item) => (item.id === revoked.id ? revoked : item)));
      if (createdKey?.id === revoked.id) {
        setCreatedKey(null);
      }
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setRevokingId(null);
    }
  }

  async function copyRawKey() {
    if (!createdKey?.raw_key) return;
    await navigator.clipboard.writeText(createdKey.raw_key);
  }

  if (!auth.ready) {
    return (
      <div className="min-h-screen">
        <TopNav />
        <main className="mx-auto flex w-full max-w-[1600px] items-center justify-center px-4 py-16">
          <div className="panel p-6 text-center">
            <Loader2 className="mx-auto mb-3 size-6 animate-spin" />
            <p className="font-semibold">Carregando acesso seguro…</p>
          </div>
        </main>
      </div>
    );
  }

  if (!auth.user || auth.user.role !== "owner") {
    return (
      <div className="min-h-screen">
        <TopNav />
        <main className="mx-auto flex w-full max-w-[1200px] items-center justify-center px-4 py-16">
          <div className="panel max-w-xl p-8 text-center">
            <ShieldCheck className="mx-auto mb-4 size-10 text-primary" />
            <h1 className="text-2xl font-bold">Acesso restrito ao dono</h1>
            <p className="mt-3 text-sm text-muted-foreground">
              Esta área gera chaves de liberação para a API pública e só deve ser aberta pelo
              usuário administrador.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              <Link
                to="/apis"
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
              >
                Ir para Central de APIs
              </Link>
              <Link
                to="/"
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-2.5 text-sm font-semibold"
              >
                Voltar ao painel
              </Link>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-[1600px] px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-medium text-foreground">
              <KeyRound className="size-3.5" aria-hidden="true" />
              API Hub · /api-hub/chaves
            </span>
            <h1 className="mt-3 text-2xl font-bold leading-tight sm:text-3xl md:text-4xl">
              Chaves de Acesso
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Gere uma chave de liberação com vencimento, copie o valor só uma vez e revogue o
              acesso quando não precisar mais. Esta é a base para o SaaS futuro consumir a API com
              segurança.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/apis"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-2.5 text-sm font-medium transition-colors hover:border-primary/50"
            >
              <BadgeCheck className="size-4" aria-hidden="true" />
              Central de APIs
            </Link>
            <button
              type="button"
              onClick={() => void load()}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-2.5 text-sm font-medium transition-colors hover:border-primary/50"
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              Recarregar
            </button>
          </div>
        </div>

        <dl className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Stat label="Chaves cadastradas" value={String(stats.total)} />
          <Stat label="Ativas agora" value={String(stats.active)} />
          <Stat label="Vencendo em 7 dias" value={String(stats.expiringSoon)} tone="warn" />
        </dl>

        {error ? (
          <p className="mb-6 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm">
            {error}
          </p>
        ) : null}

        {createdKey?.raw_key ? (
          <div className="panel mb-6 border border-primary/30 bg-primary/5 p-5">
            <p className="text-sm font-semibold text-primary">Chave criada agora</p>
            <div className="mt-3 rounded-xl border border-border bg-background/60 p-4">
              <code className="block overflow-x-auto font-mono text-sm leading-relaxed">
                {createdKey.raw_key}
              </code>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void copyRawKey()}
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground"
              >
                <Copy className="size-4" aria-hidden="true" />
                Copiar chave
              </button>
              <button
                type="button"
                onClick={() => setCreatedKey(null)}
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface/70 px-4 py-2.5 text-sm font-medium"
              >
                Fechar
              </button>
            </div>
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[1.05fr_1fr]">
          <section className="panel p-5">
            <h2 className="text-lg font-semibold">Gerar nova chave</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              O valor completo só aparece uma vez. Depois disso, o sistema mantém apenas o hash.
            </p>

            <div className="mt-5 grid gap-4">
              <label className="grid gap-2 text-sm font-medium">
                Nome da chave
                <input
                  value={label}
                  onChange={(event) => setLabel(event.target.value)}
                  className="rounded-xl border border-border bg-background/60 px-4 py-3 outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/70"
                  placeholder="Gerador Mago"
                />
              </label>
              <label className="grid gap-2 text-sm font-medium">
                Validade em dias
                <input
                  type="number"
                  min={1}
                  max={3650}
                  value={expiresDays}
                  onChange={(event) => setExpiresDays(event.target.value)}
                  className="rounded-xl border border-border bg-background/60 px-4 py-3 outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/70"
                />
              </label>
              <label className="grid gap-2 text-sm font-medium">
                Escopos
                <input
                  value={scopes}
                  onChange={(event) => setScopes(event.target.value)}
                  className="rounded-xl border border-border bg-background/60 px-4 py-3 outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/70"
                  placeholder="api, saas, public"
                />
              </label>
              <button
                type="button"
                onClick={() => void handleCreate()}
                disabled={creating}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-60"
              >
                {creating ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Plus className="size-4" aria-hidden="true" />
                )}
                Gerar chave de liberação
              </button>
            </div>
          </section>

          <section className="panel p-5">
            <h2 className="text-lg font-semibold">Chaves já emitidas</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Revogue qualquer chave comprometida ou expirada sem mexer no resto do sistema.
            </p>

            {loading ? (
              <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
                Carregando chaves…
              </div>
            ) : keys.length === 0 ? (
              <div className="mt-6 rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
                Nenhuma chave criada ainda. Use o formulário ao lado para emitir a primeira.
              </div>
            ) : (
              <div className="mt-4 grid gap-3">
                {keys.map((key) => (
                  <article
                    key={key.id}
                    className="rounded-2xl border border-border bg-surface/50 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold">{key.label}</h3>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {key.prefix} · {key.scopes.join(", ") || "sem escopos"}
                        </p>
                      </div>
                      <StatusPill status={key.status} />
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                      <div className="rounded-xl border border-border/70 bg-background/50 p-3">
                        <span className="block font-medium text-foreground">Expira em</span>
                        <span className="mt-1 inline-flex items-center gap-1.5">
                          <CalendarClock className="size-3.5" />
                          {new Date(key.expires_at).toLocaleString("pt-BR")}
                        </span>
                      </div>
                      <div className="rounded-xl border border-border/70 bg-background/50 p-3">
                        <span className="block font-medium text-foreground">Último uso</span>
                        <span className="mt-1 block">
                          {key.last_used_at
                            ? new Date(key.last_used_at).toLocaleString("pt-BR")
                            : "Nunca usada"}
                        </span>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void handleRevoke(key.id)}
                        disabled={revokingId === key.id || key.status === "revoked"}
                        className="inline-flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs font-semibold text-foreground disabled:opacity-60"
                      >
                        {revokingId === key.id ? (
                          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                        ) : (
                          <Trash2 className="size-3.5" aria-hidden="true" />
                        )}
                        Revogar
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

function StatusPill({ status }: { status: ReleaseKey["status"] }) {
  const label =
    status === "active" ? "Ativa" : status === "expired" ? "Expirada" : "Revogada";
  const tone =
    status === "active"
      ? "border-success/30 bg-success/10 text-success"
      : "border-destructive/30 bg-destructive/10 text-destructive";
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${tone}`}>
      {label}
    </span>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "warn";
}) {
  return (
    <div className="panel px-4 py-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`mt-1 text-2xl font-bold ${tone === "warn" ? "text-amber-400" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
