import { useCallback, useEffect, useState } from "react";

import { DEFAULT_STYLE, type CaptionStyle } from "./style";

const KEY = "viral.captions.draft.v1";

export type CaptionDraft = {
  style: CaptionStyle;
  transcript: string;
  mutation: string;
  sourceLabel: string;
  savedAt: number;
};

function read(): CaptionDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CaptionDraft;
    if (!parsed?.style) return null;
    return { ...parsed, style: { ...DEFAULT_STYLE, ...parsed.style } };
  } catch {
    return null;
  }
}

/**
 * Rascunho persistente do editor: fechar a tela, dar F5 ou voltar dias
 * depois mantém o mesmo estilo de legenda pronto para continuar editando.
 */
export function useCaptionDraft() {
  const [draft, setDraft] = useState<CaptionDraft | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setDraft(read());
    setHydrated(true);
  }, []);

  const save = useCallback((data: Omit<CaptionDraft, "savedAt">) => {
    const next: CaptionDraft = { ...data, savedAt: Date.now() };
    setDraft(next);
    try {
      window.localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage cheio ou bloqueado — o editor continua funcionando em memória */
    }
  }, []);

  const clear = useCallback(() => {
    setDraft(null);
    try {
      window.localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }, []);

  return { draft, hydrated, save, clear };
}
