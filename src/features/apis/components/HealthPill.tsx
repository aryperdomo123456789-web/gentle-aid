import { CheckCircle2, CircleAlert, CircleHelp, KeyRound } from "lucide-react";

import type { Provider } from "../types";

/** Selo de saúde da integração, derivado do último teste de conectividade. */
export function HealthPill({ provider }: { provider: Provider }) {
  const ok = provider.last_test?.ok;

  if (!provider.configured) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
        <CircleHelp className="size-3" aria-hidden="true" />
        Sem chave
      </span>
    );
  }
  if (ok === true) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-success/50 bg-success/15 px-3 py-1 text-xs">
        <CheckCircle2 className="size-3 text-success" aria-hidden="true" />
        Operacional
      </span>
    );
  }
  if (ok === false) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-destructive/50 bg-destructive/15 px-3 py-1 text-xs">
        <CircleAlert className="size-3 text-destructive" aria-hidden="true" />
        Falhando
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-electric/50 bg-electric/10 px-3 py-1 text-xs">
      <KeyRound className="size-3" aria-hidden="true" />
      Configurada
    </span>
  );
}
