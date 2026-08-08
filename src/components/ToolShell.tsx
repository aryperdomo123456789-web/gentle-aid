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
  subtitle: ReactNode;
  badge?: string;
  left: ReactNode;
  right: ReactNode;
  below?: ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="mx-auto w-full max-w-[1600px] px-3 py-6 sm:px-4 sm:py-8 md:px-8">
        <div className="surface-in mb-6 border-l-2 border-primary/60 pl-4 sm:mb-8 sm:pl-5">
          {badge ? (
            <span className="inline-flex items-center rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-foreground">
              {badge}
            </span>
          ) : null}
          <h1 className="mt-3 text-balance text-2xl font-bold leading-tight tracking-tight sm:text-3xl md:text-[2.5rem]">
            {title}
          </h1>
          <p className="mt-2 max-w-2xl text-pretty text-sm leading-6 text-muted-foreground">
            {subtitle}
          </p>
        </div>

        <div className="grid gap-4 sm:gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section aria-label="Controles" className="panel surface-in min-w-0 p-4 sm:p-6 md:p-7">
            {left}
          </section>
          <section
            aria-label="Status do processamento"
            className="panel surface-in min-w-0 p-4 sm:p-6 lg:sticky lg:top-28 lg:max-h-[calc(100vh-8rem)] lg:self-start lg:overflow-y-auto xl:top-36"
          >
            {right}
          </section>
        </div>

        {below ? <div className="mt-6 min-w-0 sm:mt-8">{below}</div> : null}
      </main>

      <footer className="mx-auto w-full max-w-[1600px] px-3 pb-10 text-xs text-muted-foreground sm:px-4 md:px-8">
        Jobs gravados em{" "}
        <code className="rounded bg-muted/50 px-1.5 py-0.5 font-mono">fabrica_clips/</code>
      </footer>
    </div>
  );
}
