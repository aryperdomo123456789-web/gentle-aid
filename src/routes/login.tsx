import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { KeyRound, LockKeyhole, Shield } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Field, SubmitButton, TextInput } from "@/components/form";
import { useAuth } from "@/components/AuthProvider";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Acesso seguro — Ecossistema Viral" },
      {
        name: "description",
        content:
          "Login compacto e futurista para acesso ao painel do Ecossistema Viral com sessão salva no servidor.",
      },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("mago@dono.site");
  const [password, setPassword] = useState("123698745");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (auth.ready && auth.user) {
      void navigate({ to: "/", replace: true });
    }
  }, [auth.ready, auth.user, navigate]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await auth.login(email, password);
      void navigate({ to: "/", replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao entrar no painel.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-10 md:px-6">
      <div
        className="pointer-events-none absolute inset-0 opacity-80"
        aria-hidden="true"
        style={{
          backgroundImage:
            "radial-gradient(circle at 18% 20%, color-mix(in oklab, var(--primary) 26%, transparent), transparent 28%), radial-gradient(circle at 82% 18%, color-mix(in oklab, var(--electric) 22%, transparent), transparent 24%), radial-gradient(circle at 50% 100%, color-mix(in oklab, var(--success) 12%, transparent), transparent 28%)",
        }}
      />

      <section className="panel relative z-10 w-full max-w-[980px] overflow-hidden px-5 py-5 shadow-2xl shadow-black/20 md:px-6 md:py-6">
        <div className="absolute right-0 top-0 h-24 w-24 rounded-full bg-primary/20 blur-3xl" />
        <div className="absolute -bottom-8 -left-8 h-28 w-28 rounded-full bg-electric/15 blur-3xl" />

        <div className="relative grid gap-5 lg:grid-cols-[0.95fr_1.05fr] lg:gap-6">
          <div className="space-y-4 rounded-[24px] border border-border/70 bg-background/20 p-5 md:p-6">
            <div className="flex items-center gap-3">
              <span
                className="flex size-11 items-center justify-center rounded-2xl text-sm font-bold text-primary-foreground shadow-md"
                style={{ backgroundImage: "var(--gradient-viral)" }}
                aria-hidden="true"
              >
                EV
              </span>
              <div className="leading-tight">
                <p className="text-[11px] uppercase tracking-[0.3em] text-muted-foreground">
                  Ecossistema Viral
                </p>
                <h1 className="text-2xl font-bold tracking-tight text-foreground">Login</h1>
              </div>
            </div>

            <p className="max-w-md text-sm leading-6 text-muted-foreground">
              Acesso de dono ou usuário para entrar no painel com sessão salva no servidor e
              histórico separado por conta.
            </p>

            <div className="flex flex-wrap gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-foreground">
                <Shield className="size-3.5" />
                Acesso protegido
              </span>
              <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
                <KeyRound className="size-3.5 text-electric" />
                Sessão no servidor
              </span>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              <MiniTile title="Histórico por usuário" />
              <MiniTile title="Login persistente" />
              <MiniTile title="Dono e contas comuns" />
              <MiniTile title="Fluxo SaaS multi-tenant" />
            </div>

            <div className="rounded-3xl border border-border/80 bg-surface/70 p-4">
              <div className="flex items-center gap-3">
                <span className="flex size-10 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                  <LockKeyhole className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-foreground">Conta inicial do dono</p>
                  <p className="text-xs text-muted-foreground">
                    role owner · acesso administrativo
                  </p>
                </div>
              </div>
              <div className="mt-3 grid gap-1 text-sm text-muted-foreground">
                <p>
                  Email: <span className="font-mono text-foreground">mago@dono.site</span>
                </p>
                <p>
                  Senha: <span className="font-mono text-foreground">123698745</span>
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-[24px] border border-border/80 bg-background/55 p-5 shadow-xl shadow-black/20 backdrop-blur-xl md:p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-foreground">
                <KeyRound className="size-3.5" />
                Entrar no painel
              </span>
              <span className="rounded-full border border-border bg-background/50 px-3 py-1 text-xs text-muted-foreground">
                Acesso de dono ou usuário
              </span>
            </div>

            <h2 className="text-2xl font-bold tracking-tight text-foreground">
              Entre com suas credenciais
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Use o login do dono ou do usuário para acessar a plataforma com segurança.
            </p>

            <form onSubmit={onSubmit} className="mt-5 space-y-4">
              <Field label="Email">
                {(id) => (
                  <TextInput
                    id={id}
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="username"
                    placeholder="mago@dono.site"
                    required
                  />
                )}
              </Field>

              <Field label="Senha">
                {(id) => (
                  <TextInput
                    id={id}
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    required
                  />
                )}
              </Field>

              {error ? (
                <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-foreground">
                  {error}
                </p>
              ) : null}

              <SubmitButton busy={busy}>{busy ? "Entrando…" : "Entrar"}</SubmitButton>
            </form>

            <p className="mt-4 rounded-2xl border border-border bg-background/50 px-4 py-3 text-xs leading-5 text-muted-foreground">
              Depois de entrar, o painel principal abre normalmente. A edição de credenciais fica em{" "}
              <span className="font-mono text-foreground">/conta</span>.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}

function MiniTile({ title }: { title: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/45 px-4 py-3 text-sm text-muted-foreground">
      {title}
    </div>
  );
}
