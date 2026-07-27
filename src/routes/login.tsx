import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { LockKeyhole } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { TextInput } from "@/components/form";
import { useAuth } from "@/components/AuthProvider";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Painel Admin — Ecossistema Viral" },
      {
        name: "description",
        content: "Acesso restrito ao painel do Ecossistema Viral com sessão salva no servidor.",
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
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#02050f] px-4 py-10">
      <div
        className="pointer-events-none absolute inset-0"
        aria-hidden="true"
        style={{
          backgroundImage:
            "radial-gradient(circle at 50% 18%, rgba(19, 132, 255, 0.22), transparent 22%), radial-gradient(circle at 50% 18%, rgba(141, 92, 246, 0.16), transparent 34%), radial-gradient(circle at 12% 36%, rgba(43, 108, 255, 0.12), transparent 18%), radial-gradient(circle at 88% 64%, rgba(43, 108, 255, 0.12), transparent 18%)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.18]"
        aria-hidden="true"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <section className="relative z-10 w-full max-w-[980px] rounded-[28px] border border-cyan-500/10 bg-[#0a1020]/95 px-6 py-10 shadow-[0_0_0_1px_rgba(0,255,255,0.04),0_0_70px_rgba(21,145,255,0.18)] backdrop-blur-xl md:px-10 md:py-12">
        <div className="mx-auto flex w-full max-w-[460px] flex-col items-center">
          <div className="mb-7 flex size-18 items-center justify-center rounded-[26px] bg-[linear-gradient(135deg,#05d3ff_0%,#73a4ff_45%,#b36bff_100%)] shadow-[0_0_30px_rgba(50,192,255,0.45)]">
            <LockKeyhole className="size-9 text-slate-950" aria-hidden="true" />
          </div>

          <h1 className="text-center text-[2.05rem] font-black tracking-tight text-slate-100 md:text-[2.35rem]">
            Painel Admin
          </h1>
          <p className="mt-3 text-center text-base text-slate-400">Acesso restrito</p>

          <form onSubmit={onSubmit} className="mt-8 w-full space-y-4">
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-slate-100" htmlFor="login-email">
                E-mail
              </label>
              <TextInput
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                placeholder="mago@dono.site"
                required
                className="h-[58px] rounded-[20px] border-2 border-cyan-400/80 bg-[#e8efff] px-4 text-[15px] text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] placeholder:text-slate-500 focus:border-cyan-300 focus:ring-4 focus:ring-cyan-400/20"
              />
            </div>

            <div className="space-y-2">
              <label
                className="block text-sm font-semibold text-slate-100"
                htmlFor="login-password"
              >
                Senha
              </label>
              <TextInput
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••"
                required
                className="h-[58px] rounded-[20px] border-2 border-cyan-400/80 bg-[#e8efff] px-4 text-[15px] text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)] placeholder:text-slate-500 focus:border-cyan-300 focus:ring-4 focus:ring-cyan-400/20"
              />
            </div>

            {error ? (
              <p className="rounded-[18px] border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={busy}
              className="flex h-[58px] w-full items-center justify-center rounded-[20px] bg-[linear-gradient(135deg,#09cfff_0%,#5ea4ff_54%,#b56dff_100%)] text-[15px] font-semibold text-slate-950 shadow-[0_10px_35px_rgba(56,154,255,0.35)] transition-transform hover:translate-y-[-1px] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {busy ? "Entrando…" : "Entrar"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
