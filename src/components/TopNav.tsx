import { Link } from "@tanstack/react-router";
import {
  Download,
  Music2,
  Captions,
  AudioLines,
  Sparkles,
  History,
  KeyRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type Tool = { to: string; label: string; icon: LucideIcon };

export const TOOLS: Tool[] = [
  { to: "/", label: "YouTube Bypass", icon: Download },
  { to: "/tiktok", label: "TikTok Dashboard", icon: Music2 },
  { to: "/legendar", label: "Legendar", icon: Captions },
  { to: "/voice-conversion", label: "Voz V2V", icon: AudioLines },
  { to: "/canva-cleaner", label: "Canva Cleaner", icon: Sparkles },
  { to: "/historico", label: "Histórico", icon: History },
  { to: "/apis", label: "Central de APIs", icon: KeyRound },
];

export function TopNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 md:px-8">
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
              Pipeline FFmpeg · bypass algorítmico · aaPanel
            </p>
          </div>
        </div>

        <nav aria-label="Ferramentas" className="-mx-1 overflow-x-auto pb-1">
          <ul className="flex min-w-max items-center gap-2 px-1">
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
