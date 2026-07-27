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
      <main className="mx-auto w-full max-w-[1600px] px-4 py-8 md:px-8">
        <div className="mb-8">
          {badge ? (
            <span className="inline-flex items-center rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-medium text-foreground">
              {badge}
            </span>
          ) : null}
          <h1 className="mt-3 text-3xl font-bold md:text-4xl">{title}</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section aria-label="Controles" className="panel p-6">
            {left}
          </section>
          <section
            aria-label="Status do processamento"
            className="panel p-6 lg:sticky lg:top-36 lg:self-start"
          >
            {right}
          </section>
        </div>

        {below ? <div className="mt-6">{below}</div> : null}
      </main>

      <footer className="mx-auto w-full max-w-[1600px] px-4 pb-10 text-xs text-muted-foreground md:px-8">
        Jobs gravados em <code className="font-mono">fabrica_clips/</code>
      </footer>
    </div>
  );
}
