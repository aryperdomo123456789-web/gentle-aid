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
          "Login futurista para acesso de dono e usuários ao painel SaaS do Ecossistema Viral.",
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
      const session = auth.login(email, password);
      if (!session) {
        setError("Credenciais inválidas. Verifique o acesso do dono ou do usuário.");
        return;
      }
      void navigate({ to: "/", replace: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-background px-4 py-10 md:px-8">
      <div
        className="pointer-events-none absolute inset-0 opacity-80"
        aria-hidden="true"
        style={{
          backgroundImage:
            "radial-gradient(circle at 18% 20%, color-mix(in oklab, var(--primary) 28%, transparent), transparent 28%), radial-gradient(circle at 82% 18%, color-mix(in oklab, var(--electric) 24%, transparent), transparent 26%), radial-gradient(circle at 50% 100%, color-mix(in oklab, var(--success) 14%, transparent), transparent 30%)",
        }}
      />

      <div className="relative mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-[1200px] items-center">
        <section className="panel relative w-full overflow-hidden px-6 py-7 md:px-8">
          <div className="absolute right-0 top-0 h-28 w-28 rounded-full bg-primary/20 blur-3xl" />
          <div className="absolute -bottom-6 -left-6 h-28 w-28 rounded-full bg-electric/15 blur-3xl" />

          <div className="relative mx-auto grid w-full max-w-4xl gap-8 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <span
                  className="flex size-11 items-center justify-center rounded-2xl text-sm font-bold text-primary-foreground shadow-md"
                  style={{ backgroundImage: "var(--gradient-viral)" }}
                  aria-hidden="true"
                >
                  EV
                </span>
                <div className="leading-tight">
                  <p className="text-[11px] uppercase tracking-[0.26em] text-muted-foreground">
                    Ecossistema Viral
                  </p>
                  <h1 className="text-2xl font-bold tracking-tight text-foreground">Login</h1>
                </div>
              </div>

              <p className="max-w-sm text-sm leading-6 text-muted-foreground">
                Acesso de dono ou usuário para continuar no painel e manter os históricos separados.
              </p>

              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium">
                  <Shield className="size-3.5" />
                  Acesso protegido
                </span>
                <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
                  <KeyRound className="size-3.5 text-electric" />
                  Login do painel
                </span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <InfoTile title="Sessão separada por usuário" />
                <InfoTile title="Histórico individual por login" />
                <InfoTile title="Base pronta para owner + comuns" />
                <InfoTile title="Fluxo compatível com SaaS multi-tenant" />
              </div>

              <div className="rounded-3xl border border-border/80 bg-surface/70 p-5">
                <div className="flex items-center gap-3">
                  <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                    <LockKeyhole className="size-5" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Conta inicial do dono</p>
                    <p className="text-xs text-muted-foreground">
                      role owner · acesso administrativo
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 text-sm text-muted-foreground">
                  <p>
                    Email: <span className="font-mono text-foreground">mago@dono.site</span>
                  </p>
                  <p>
                    Senha: <span className="font-mono text-foreground">123698745</span>
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-border/80 bg-background/55 p-6 shadow-xl shadow-black/20 backdrop-blur-xl">
              <div className="mb-5 flex items-center justify-between gap-3">
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
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Use o login do dono ou do usuário para acessar a plataforma com segurança.
              </p>

              <form onSubmit={onSubmit} className="mt-6 space-y-4">
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

              <p className="mt-5 rounded-2xl border border-border bg-background/50 px-4 py-3 text-xs leading-5 text-muted-foreground">
                Depois de entrar, o painel principal abre normalmente. A edição de credenciais fica
                em <span className="font-mono text-foreground">/conta</span>.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function InfoTile({ title }: { title: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/45 px-4 py-4 text-sm text-muted-foreground">
      {title}
    </div>
  );
}
