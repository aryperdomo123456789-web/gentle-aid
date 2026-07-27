import { Link } from "@tanstack/react-router";
import {
  Download,
  Music2,
  Captions,
  AudioLines,
  Sparkles,
  History,
  Radar,
  KeyRound,
  LogOut,
  Shield,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { useAuth } from "@/components/AuthProvider";

type Tool = { to: string; label: string; icon: LucideIcon };

export const TOOLS: Tool[] = [
  { to: "/", label: "Desvio YouTube", icon: Download },
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
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 px-4 py-4 md:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              className="flex size-9 items-center justify-center rounded-xl text-sm font-bold text-primary-foreground"
              style={{ backgroundImage: "var(--gradient-viral)" }}
              aria-hidden="true"
            >
              EV
            </span>
            <div className="leading-tight">
              <p className="font-display text-base font-bold tracking-tight">
                Ecossistema <span className="text-gradient-viral">Viral</span>
              </p>
              <p className="text-xs text-muted-foreground">
                Pipeline FFmpeg · desvio algorítmico · aaPanel
              </p>
            </div>
          </div>

          {auth.user ? (
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1.5 text-xs font-medium text-muted-foreground">
                <Shield className="size-3.5 text-success" aria-hidden="true" />
                {auth.user.name} · {auth.user.role === "owner" ? "dono" : "usuário"}
              </span>
              <span className="hidden rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs font-mono text-muted-foreground md:inline-flex">
                {auth.user.email}
              </span>
              <button
                type="button"
                onClick={() => auth.logout()}
                className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1.5 text-xs font-semibold text-foreground hover:border-primary/50"
              >
                <LogOut className="size-3.5" aria-hidden="true" />
                Sair
              </button>
            </div>
          ) : null}
        </div>

        <nav aria-label="Ferramentas" className="-mx-1 pb-1">
          <ul className="flex flex-wrap items-center gap-2 px-1">
            {TOOLS.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <Link
                  to={to}
                  activeOptions={{ exact: to === "/" }}
                  className="flex items-center gap-2 rounded-full border border-border/80 bg-surface/70 px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground data-[status=active]:border-transparent data-[status=active]:bg-primary data-[status=active]:text-primary-foreground"
                >
                  <Icon className="size-4" aria-hidden="true" />
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
