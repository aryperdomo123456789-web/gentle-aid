import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Bot, KeyRound, Shield, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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

  const features = useMemo(
    () => [
      "Sessão separada por usuário",
      "Base pronta para owner + comuns",
      "Histórico individual por login",
      "Fluxo compatível com SaaS multi-tenant",
    ],
    [],
  );

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const session = auth.login(email, password);
      if (!session) {
        setError("Credenciais inválidas. Verifique o acesso de dono ou usuário.");
        return;
      }
      void navigate({ to: "/", replace: true });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-background px-4 py-8 md:px-8">
      <div
        className="pointer-events-none absolute inset-0 opacity-80"
        aria-hidden="true"
        style={{
          backgroundImage:
            "radial-gradient(circle at 18% 20%, color-mix(in oklab, var(--primary) 28%, transparent), transparent 28%), radial-gradient(circle at 82% 18%, color-mix(in oklab, var(--electric) 24%, transparent), transparent 26%), radial-gradient(circle at 50% 100%, color-mix(in oklab, var(--success) 14%, transparent), transparent 30%)",
        }}
      />

      <div className="relative mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-6xl items-center">
        <div className="grid w-full gap-8 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="panel relative overflow-hidden p-8 md:p-10">
            <div className="absolute right-0 top-0 h-44 w-44 rounded-full bg-primary/20 blur-3xl" />
            <div className="absolute -bottom-10 -left-10 h-44 w-44 rounded-full bg-electric/15 blur-3xl" />

            <div className="relative space-y-6">
              <div className="flex flex-wrap items-center gap-3">
                <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium">
                  <Shield className="size-3.5" />
                  Acesso protegido
                </span>
                <span className="inline-flex items-center gap-2 rounded-full border border-border bg-background/60 px-3 py-1 text-xs font-medium text-muted-foreground">
                  <Sparkles className="size-3.5 text-electric" />
                  SaaS multiusuário em preparo
                </span>
              </div>

              <div>
                <p className="mb-2 text-xs uppercase tracking-[0.25em] text-muted-foreground">
                  Ecossistema Viral
                </p>
                <h1 className="max-w-xl text-4xl font-bold leading-tight md:text-6xl">
                  Login futurista para o seu painel{" "}
                  <span className="text-gradient-viral">SaaS</span>
                </h1>
                <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground md:text-base">
                  Primeira camada do sistema de dono e usuários. Depois do acesso, cada conta pode
                  ganhar histórico próprio, jobs próprios e isolamento total de dados.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {features.map((item) => (
                  <div
                    key={item}
                    className="rounded-2xl border border-border bg-background/50 p-4 text-sm text-muted-foreground"
                  >
                    {item}
                  </div>
                ))}
              </div>

              <div className="rounded-2xl border border-border bg-background/50 p-4">
                <div className="flex items-center gap-3">
                  <div className="flex size-11 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                    <Bot className="size-5" aria-hidden="true" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold">Conta inicial do dono</p>
                    <p className="text-xs text-muted-foreground">
                      role owner · acesso administrativo
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid gap-2 text-xs text-muted-foreground">
                  <p>
                    Email: <span className="font-mono text-foreground">mago@dono.site</span>
                  </p>
                  <p>
                    Senha: <span className="font-mono text-foreground">123698745</span>
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section className="panel p-6 md:p-8">
            <div className="mb-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium">
                <KeyRound className="size-3.5" aria-hidden="true" />
                Entrar no painel
              </div>
              <h2 className="mt-4 text-2xl font-bold">Acesso de dono ou usuário</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Entre com suas credenciais para carregar seu ambiente e manter o histórico separado.
              </p>
            </div>

            <form onSubmit={onSubmit} className="space-y-5">
              <Field label="Email">
                {(id) => (
                  <TextInput
                    id={id}
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="username"
                    placeholder="voce@empresa.site"
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
                    placeholder="Sua senha"
                    required
                  />
                )}
              </Field>

              {error ? (
                <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-foreground">
                  {error}
                </p>
              ) : null}

              <SubmitButton busy={busy}>{busy ? "Entrando…" : "Acessar painel"}</SubmitButton>
            </form>

            <div className="mt-6 rounded-2xl border border-border bg-background/50 p-4 text-xs text-muted-foreground">
              Próximo passo do SaaS: autenticação de múltiplos usuários, permissões e histórico
              isolado por conta.
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
