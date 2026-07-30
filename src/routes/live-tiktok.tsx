import { createFileRoute } from "@tanstack/react-router";

import { LiveStation } from "@/features/live/components/LiveStation";

export const Route = createFileRoute("/live-tiktok")({
  head: () => ({
    meta: [
      { title: "Live 24/7 no TikTok — Ecossistema Viral" },
      {
        name: "description",
        content:
          "Transmita vídeos em loop no TikTok LIVE via RTMP com overlay dinâmico, watchdog de reconexão e preset vertical 9:16.",
      },
      { property: "og:title", content: "Live 24/7 no TikTok — Ecossistema Viral" },
      {
        property: "og:description",
        content: "Loop vertical 9:16 com reconexão automática e chave RTMP guardada com segurança.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LiveTikTokPage,
});

function LiveTikTokPage() {
  return (
    <LiveStation
      platform="tiktok"
      badge="Estação de Live · TikTok"
      title="Live 24/7 no TikTok"
      subtitle="Loop vertical 9:16 com overlay dinâmico e watchdog — a live segue de pé mesmo se o RTMP oscilar."
      warning="O TikTok libera RTMP a partir de 1.000 seguidores (LIVE Studio / LIVE Center). A chave é regenerada a cada nova live: gere no app, cole aqui e só então inicie. Use vídeos verticais 9:16 para não perder enquadramento."
      keyHelp="O TikTok entrega a URL no LIVE Center (algo como rtmp://push.tiktokcdn.com/live/)."
    />
  );
}
