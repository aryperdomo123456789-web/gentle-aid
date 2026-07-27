import { useCallback, useState } from "react";

import { Field, SelectInput, SubmitButton, TextInput } from "@/components/form";
import { apiPostJson, friendlyError } from "@/lib/api";

export type DiscoveryCard = {
  id: string;
  platform: string;
  url: string;
  embed_url: string | null;
  thumbnail: string | null;
  author: string;
  nickname: string;
  title: string;
  desc: string;
  views_label: string;
  likes_label: string;
  comments_label: string;
  shares_label: string;
  duration_label: string;
  published_label: string;
};

type SearchResponse = {
  results: DiscoveryCard[];
  sources: string[];
};

const REGIONS = ["BR", "US", "MX", "PT", "ES", "FR", "DE", "IT", "JP", "ID"];

const PLATFORMS = [
  { value: "auto", label: "Auto (TikTok + YouTube)" },
  { value: "tiktok", label: "TikTok" },
  { value: "youtube", label: "YouTube / Shorts" },
];

/**
 * Fluxo de pesquisa do legado, unificado: busca por palavra-chave, `@perfil`
 * ou URL → cards com descrição e métricas → player embutido para assistir
 * antes de mandar o conteúdo para a esteira de codagem da ferramenta.
 */
export function DiscoveryPanel({
  title = "Pesquisa viral · assista antes de codar",
  hint = "Palavra-chave, @perfil ou URL direta. Veja métricas e o vídeo antes de processar.",
  defaultPlatform = "auto",
  actionLabel,
  onAction,
  actionBusyUrl,
}: {
  title?: string;
  hint?: string;
  defaultPlatform?: string;
  actionLabel: string;
  onAction: (card: DiscoveryCard) => void;
  actionBusyUrl?: string | null;
}) {
  const [query, setQuery] = useState("");
  const [platform, setPlatform] = useState(defaultPlatform);
  const [region, setRegion] = useState("BR");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cards, setCards] = useState<DiscoveryCard[]>([]);
  const [searched, setSearched] = useState(false);
  const [player, setPlayer] = useState<DiscoveryCard | null>(null);

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const q = query.trim();
      if (!q) return;
      setBusy(true);
      setError(null);
      try {
        const data = await apiPostJson<SearchResponse>("/api/discover/search", {
          query: q,
          platform,
          region,
          limit: 18,
        });
        setCards(data.results ?? []);
      } catch (err) {
        setError(friendlyError(err));
        setCards([]);
      } finally {
        setSearched(true);
        setBusy(false);
      }
    },
    [platform, query, region],
  );

  return (
    <section className="panel p-6" aria-label="Pesquisa de conteúdo viral">
      <header className="mb-4">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{hint}</p>
      </header>

      <form onSubmit={submit} className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
        <Field label="Busca">
          {(id) => (
            <TextInput
              id={id}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="ex.: renda extra · @criador · https://tiktok.com/@user/video/123"
              maxLength={300}
            />
          )}
        </Field>
        <Field label="Plataforma">
          {(id) => (
            <SelectInput id={id} value={platform} onChange={(e) => setPlatform(e.target.value)}>
              {PLATFORMS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </SelectInput>
          )}
        </Field>
        <Field label="Região">
          {(id) => (
            <SelectInput id={id} value={region} onChange={(e) => setRegion(e.target.value)}>
              {REGIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </SelectInput>
          )}
        </Field>
        <SubmitButton busy={busy}>{busy ? "Buscando…" : "Buscar virais"}</SubmitButton>
      </form>

      {error ? (
        <p className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive-foreground">
          {error}
        </p>
      ) : null}

      {searched && !busy && cards.length === 0 && !error ? (
        <p className="mt-4 text-sm text-muted-foreground">
          Nenhum pico de tráfego orgânico localizado para esse termo. Tente outra palavra-chave,
          um @perfil ou cole a URL direta do vídeo.
        </p>
      ) : null}

      {cards.length > 0 ? (
        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cards.map((card) => {
            const running = actionBusyUrl === card.url;
            return (
              <article
                key={card.id + card.url}
                className="flex flex-col justify-between rounded-xl border border-border bg-background/50 p-4 transition hover:border-primary/40"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-bold">@{card.author}</h3>
                      <p className="truncate text-xs text-muted-foreground">{card.nickname}</p>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        {card.published_label} · {card.duration_label} · {card.platform}
                      </p>
                    </div>
                    <span className="shrink-0 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs font-semibold">
                      {card.views_label} views
                    </span>
                  </div>

                  {card.thumbnail ? (
                    <img
                      src={card.thumbnail}
                      alt={`Miniatura do vídeo de @${card.author}`}
                      loading="lazy"
                      className="mt-3 h-40 w-full rounded-lg object-cover"
                    />
                  ) : null}

                  <p className="mt-3 line-clamp-3 text-sm italic text-muted-foreground">
                    “{card.desc}”
                  </p>
                </div>

                <div className="mt-4 border-t border-border pt-3">
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span>❤ {card.likes_label}</span>
                    <span>💬 {card.comments_label}</span>
                    <span>↗ {card.shares_label}</span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setPlayer(card)}
                      className="rounded-lg border border-border px-3 py-2 text-xs font-semibold transition hover:border-primary/50"
                    >
                      ▶ Assistir
                    </button>
                    <button
                      type="button"
                      disabled={running}
                      onClick={() => onAction(card)}
                      className="rounded-lg bg-primary px-3 py-2 text-xs font-bold text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
                    >
                      {running ? "Processando…" : actionLabel}
                    </button>
                    <a
                      href={card.url}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-lg border border-border px-3 py-2 text-xs font-semibold text-muted-foreground transition hover:border-primary/50"
                    >
                      Abrir original
                    </a>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}

      {player ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Prévia do vídeo de @${player.author}`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/85 p-4 backdrop-blur-sm"
          onClick={() => setPlayer(null)}
        >
          <div
            className="panel w-full max-w-xl p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold">@{player.author}</p>
                <p className="line-clamp-2 text-xs text-muted-foreground">{player.desc}</p>
              </div>
              <button
                type="button"
                onClick={() => setPlayer(null)}
                className="rounded-lg border border-border px-3 py-1.5 text-xs font-semibold"
              >
                Fechar
              </button>
            </div>
            <div className="aspect-video w-full overflow-hidden rounded-xl bg-black">
              {player.embed_url ? (
                <iframe
                  title={`Player · @${player.author}`}
                  src={player.embed_url}
                  className="h-full w-full"
                  allow="accelerometer; autoplay; encrypted-media; picture-in-picture"
                  allowFullScreen
                />
              ) : (
                <a
                  href={player.url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex h-full w-full items-center justify-center text-sm text-muted-foreground"
                >
                  Abrir no site original
                </a>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>{player.views_label} views</span>
              <span>❤ {player.likes_label}</span>
              <span>💬 {player.comments_label}</span>
              <span>↗ {player.shares_label}</span>
              <span>{player.duration_label}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                onAction(player);
                setPlayer(null);
              }}
              className="mt-4 w-full rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground transition hover:opacity-90"
            >
              {actionLabel}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
