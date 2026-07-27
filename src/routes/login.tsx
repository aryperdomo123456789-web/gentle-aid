import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { KeyRound, Shield } from "lucide-react";
import { useEffect, useState } from "react";

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
    <main className="relative min-h-screen overflow-hidden bg-background px-4 py-10 md:px-8">
      <div
        className="pointer-events-none absolute inset-0 opacity-80"
        aria-hidden="true"
        style={{
          backgroundImage:
            "radial-gradient(circle at 18% 20%, color-mix(in oklab, var(--primary) 28%, transparent), transparent 28%), radial-gradient(circle at 82% 18%, color-mix(in oklab, var(--electric) 24%, transparent), transparent 26%), radial-gradient(circle at 50% 100%, color-mix(in oklab, var(--success) 14%, transparent), transparent 30%)",
        }}
      />
      <div className="relative mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-[440px] items-center">
        <section className="panel w-full overflow-hidden px-6 py-7 md:px-8">
          <div className="absolute right-0 top-0 h-28 w-28 rounded-full bg-primary/20 blur-3xl" />
          <div className="absolute -bottom-6 -left-6 h-28 w-28 rounded-full bg-electric/15 blur-3xl" />

          <div className="relative space-y-5">
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

            <form onSubmit={onSubmit} className="space-y-4 pt-2">
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

            <p className="rounded-2xl border border-border bg-background/50 px-4 py-3 text-xs leading-5 text-muted-foreground">
              Use a conta do dono para administrar o painel. O resto dos usuários entra com o mesmo
              login depois que eu ligar o cadastro multiusuário.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
