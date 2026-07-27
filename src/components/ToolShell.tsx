import type { ReactNode } from "react";

import { TopNav } from "./TopNav";

export function ToolShell({
  title,
  subtitle,
  badge,
  left,
  right,
  below,
}: {
  title: string;
  subtitle: string;
  badge?: string;
  left: ReactNode;
  right: ReactNode;
  below?: ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-[1600px] px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <div className="mb-6 sm:mb-8">
          {badge ? (
            <span className="inline-flex items-center rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-medium text-foreground">
              {badge}
            </span>
          ) : null}
          <h1 className="mt-3 text-2xl font-bold leading-tight sm:text-3xl md:text-4xl">{title}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{subtitle}</p>
        </div>

        <div className="grid gap-4 sm:gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section aria-label="Controles" className="panel min-w-0 p-4 sm:p-6">
            {left}
          </section>
          <section
            aria-label="Status do processamento"
            className="panel min-w-0 p-4 sm:p-6 lg:sticky lg:top-28 lg:max-h-[calc(100vh-8rem)] lg:self-start lg:overflow-y-auto xl:top-36"
          >
            {right}
          </section>
        </div>

        {below ? <div className="mt-6 min-w-0">{below}</div> : null}
      </main>

      <footer className="mx-auto w-full max-w-[1600px] px-3 pb-10 text-xs text-muted-foreground sm:px-4 md:px-8">
        Jobs gravados em <code className="font-mono">fabrica_clips/</code>
      </footer>
    </div>
  );
}
