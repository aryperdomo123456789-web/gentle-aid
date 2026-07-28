import { Link, useNavigate } from "@tanstack/react-router";
import {
  Download,
  Music2,
  Captions,
  AudioLines,
  Sparkles,
  History,
  Radar,
  KeyRound,
  UserCog,
  LogOut,
  Shield,
  Clapperboard,
  Film,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";

type Tool = { to: string; label: string; icon: LucideIcon };

export const TOOLS: Tool[] = [
  { to: "/", label: "Desvio YouTube", icon: Download },
  { to: "/estudio", label: "Estúdio de Vídeo IA", icon: Clapperboard },
  { to: "/recap", label: "Recap Narrado", icon: Film },
  { to: "/tiktok", label: "Painel TikTok", icon: Music2 },
  { to: "/legendar", label: "Legendar", icon: Captions },
  { to: "/voice-conversion", label: "Voz V2V", icon: AudioLines },
  { to: "/canva-cleaner", label: "Limpeza Canva", icon: Sparkles },
  { to: "/radar", label: "Radar Global", icon: Radar },
  { to: "/historico", label: "Central de Jobs", icon: History },
  { to: "/apis", label: "Central de APIs", icon: KeyRound },
];

export function TopNav() {
  const auth = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await auth.logout();
    void navigate({ to: "/login", replace: true });
  }

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 shadow-[0_1px_0_0_rgba(255,255,255,0.04)] backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-3 px-3 py-3 sm:px-4 sm:py-4 md:gap-4 md:px-8">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:flex sm:flex-wrap sm:justify-between">
          <Link
            to="/"
            className="group flex min-w-0 items-center gap-2 rounded-xl transition-opacity hover:opacity-90 sm:gap-3"
          >
            <span
              className="flex size-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-primary-foreground shadow-lg shadow-primary/25 transition-transform duration-200 group-hover:scale-105"
              style={{ backgroundImage: "var(--gradient-viral)" }}
              aria-hidden="true"
            >
              EV
            </span>
            <span className="min-w-0 leading-tight">
              <span className="block truncate font-display text-sm font-bold tracking-tight sm:text-base">
                Ecossistema <span className="text-gradient-viral">Viral</span>
              </span>
              <span className="hidden truncate text-xs text-muted-foreground sm:block">
                Pipeline FFmpeg · desvio algorítmico · aaPanel
              </span>
            </span>
          </Link>

          {auth.user ? (
            <div className="flex min-w-0 shrink-0 items-center gap-1.5 sm:gap-2">
              <span className="hidden max-w-[220px] items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1.5 text-xs font-medium text-muted-foreground sm:inline-flex">
                <Shield className="size-3.5 shrink-0 text-success" aria-hidden="true" />
                <span className="truncate">
                  {auth.user.name} · {auth.user.role === "owner" ? "dono" : "usuário"}
                </span>
              </span>
              <span className="hidden max-w-[240px] truncate rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs font-mono text-muted-foreground lg:inline-flex">
                {auth.user.email}
              </span>
              <Link
                to="/conta"
                aria-label="Conta"
                className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1.5 text-xs font-semibold text-foreground transition-all duration-200 hover:border-primary/50 hover:bg-primary/10 active:scale-95"
              >
                <UserCog className="size-4 shrink-0" aria-hidden="true" />
                <span className="hidden sm:inline">Conta</span>
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                aria-label="Sair"
                className="inline-flex min-h-10 items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1.5 text-xs font-semibold text-foreground transition-all duration-200 hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive active:scale-95"
              >
                <LogOut className="size-4 shrink-0" aria-hidden="true" />
                <span className="hidden sm:inline">Sair</span>
              </button>
            </div>
          ) : null}
        </div>

        <nav
          aria-label="Ferramentas"
          className="scroll-x -mx-3 overflow-x-auto pb-1 sm:-mx-1 sm:overflow-visible"
        >
          <ul className="flex w-max items-center gap-1.5 px-3 sm:w-auto sm:flex-wrap sm:px-1">
            {TOOLS.map(({ to, label, icon: Icon }) => (
              <li key={to} className="shrink-0">
                <Link
                  to={to}
                  activeOptions={{ exact: to === "/" }}
                  className="flex min-h-10 items-center gap-2 whitespace-nowrap rounded-full border border-border/70 bg-surface/60 px-3.5 py-2 text-[13px] font-medium text-muted-foreground transition-all duration-200 hover:border-primary/50 hover:bg-primary/10 hover:text-foreground active:scale-[0.97] data-[status=active]:border-transparent data-[status=active]:bg-primary data-[status=active]:text-primary-foreground data-[status=active]:shadow-lg data-[status=active]:shadow-primary/25 sm:px-4 sm:text-sm"
                >
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}

