import { ListChecks } from "lucide-react";

export type LiveGuideStep = {
  title: string;
  detail: string;
};

/**
 * Passo a passo da plataforma — guia o operador da geração da chave RTMP
 * até a confirmação de que a live está no ar.
 */
export function LiveGuide({ title, steps }: { title: string; steps: LiveGuideStep[] }) {
  return (
    <section className="rounded-xl border border-border bg-background/40 p-4">
      <div className="flex items-center gap-2">
        <ListChecks className="size-4 text-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      </div>
      <ol className="mt-3 space-y-3">
        {steps.map((step, index) => (
          <li key={step.title} className="flex gap-3">
            <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border border-primary/40 bg-primary/10 text-[11px] font-semibold text-primary">
              {index + 1}
            </span>
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-foreground">{step.title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
