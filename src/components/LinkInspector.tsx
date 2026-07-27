import { useCallback, useState } from "react";

import type { DiscoveryCard } from "@/components/DiscoveryPanel";
import { apiPostJson, friendlyError } from "@/lib/api";

export type InspectedCard = DiscoveryCard & {
  caption?: string;
  caption_lang?: string | null;
};

/**
 * Analisa um link direto (YouTube/TikTok) antes do processamento:
 * métricas (curtidas, comentários, compartilhamentos), legenda transcrita e
 * player embutido para assistir antes de mandar para a esteira.
 */
export function LinkInspector({
  url,
  onInspected,
  actionLabel,
  onAction,
  actionBusy = false,
}: {
  url: string;
  onInspected?: (card: InspectedCard | null) => void;
  actionLabel: string;
  onAction: (card: InspectedCard) => void;
  actionBusy?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [card, setCard] = useState<InspectedCard | null>(null);
  const [showPlayer, setShowPlayer] = useState(false);
  const [showCaption, setShowCaption] = useState(false);

  const inspect = useCallback(async () => {
    const target = url.trim();
    if (target.length < 8) {
      setError("Cole um link válido do YouTube ou TikTok.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const data = await apiPostJson<{ card: InspectedCard }>("/api/discover/inspect", {
        url: target,
        captions: true,
      });
      setCard(data.card);
      setShowPlayer(true);
      onInspected?.(data.card);
    } catch (err) {
      setError(friendlyError(err));
      setCard(null);
      onInspected?.(null);
    } finally {
      setBusy(false);
    }
  }, [onInspected, url]);

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => void inspect()}
        disabled={busy}
        className="w-full rounded-xl border border-border bg-surface/60 px-4 py-2.5 text-xs font-semibold transition hover:border-primary/50 disabled:opacity-60 sm:w-auto"
      >
        {busy ? "Lendo o vídeo…" : "🔎 Analisar link (métricas + legenda)"}
      </button>

      {error ? (
        <p className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs">
          {error}
        </p>
      ) : null}

      {card ? (
        <article className="rounded-xl border border-border bg-background/50 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <p className="truncate text-sm font-bold">@{card.author}</p>
              <p className="line-clamp-2 text-xs text-muted-foreground">{card.title}</p>
              <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                {card.platform} · {card.published_label} · {card.duration_label}
              </p>
            </div>
            {card.thumbnail ? (
              <img
                src={card.thumbnail}
                alt={`Miniatura do vídeo de @${card.author}`}
                loading="lazy"
                className="h-24 w-full rounded-lg object-cover sm:w-40"
              />
            ) : null}
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              ["Views", card.views_label],
              ["Curtidas", card.likes_label],
              ["Comentários", card.comments_label],
              ["Compartilh.", card.shares_label],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-border bg-surface/50 px-3 py-2">
                <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
                <p className="text-sm font-semibold">{value}</p>
              </div>
            ))}
          </div>

          {card.desc ? (
            <p className="mt-3 line-clamp-3 text-xs italic text-muted-foreground">“{card.desc}”</p>
          ) : null}

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setShowPlayer((v) => !v)}
              className="rounded-lg border border-border px-3 py-2 text-xs font-semibold transition hover:border-primary/50"
            >
              {showPlayer ? "Ocultar player" : "▶ Assistir antes de dublar"}
            </button>
            <button
              type="button"
              onClick={() => setShowCaption((v) => !v)}
              disabled={!card.caption}
              className="rounded-lg border border-border px-3 py-2 text-xs font-semibold transition hover:border-primary/50 disabled:opacity-50"
            >
              {card.caption
                ? `${showCaption ? "Ocultar" : "📝 Ver"} legenda${card.caption_lang ? ` (${card.caption_lang})` : ""}`
                : "Sem legenda disponível"}
            </button>
            <button
              type="button"
              disabled={actionBusy}
              onClick={() => onAction(card)}
              className="rounded-lg bg-primary px-3 py-2 text-xs font-bold text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
            >
              {actionBusy ? "Processando…" : actionLabel}
            </button>
          </div>

          {showPlayer ? (
            <div className="mt-3 aspect-video w-full overflow-hidden rounded-xl bg-black">
              {card.embed_url ? (
                <iframe
                  title={`Player · @${card.author}`}
                  src={card.embed_url}
                  className="h-full w-full"
                  allow="accelerometer; autoplay; encrypted-media; picture-in-picture"
                  allowFullScreen
                />
              ) : (
                <a
                  href={card.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex h-full w-full items-center justify-center text-sm text-muted-foreground"
                >
                  Abrir no site original
                </a>
              )}
            </div>
          ) : null}

          {showCaption && card.caption ? (
            <div className="mt-3 max-h-56 overflow-y-auto rounded-xl border border-border bg-surface/40 p-3 text-xs leading-relaxed text-muted-foreground">
              {card.caption}
            </div>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}
