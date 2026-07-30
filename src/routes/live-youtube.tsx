import { createFileRoute } from "@tanstack/react-router";

import { LiveStation } from "@/features/live/components/LiveStation";

export const Route = createFileRoute("/live-youtube")({
  head: () => ({
    meta: [
      { title: "Live 24/7 no YouTube — Ecossistema Viral" },
      {
        name: "description",
        content:
          "Coloque vídeos longos em loop no YouTube Live com RTMP estável, overlay dinâmico e reconexão automática por dias seguidos.",
      },
      { property: "og:title", content: "Live 24/7 no YouTube — Ecossistema Viral" },
      {
        property: "og:description",
        content: "Loop infinito com watchdog de reconexão e overlay anti-conteúdo-estático.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LiveYouTubePage,
});

function LiveYouTubePage() {
  return (
    <LiveStation
      platform="youtube"
      badge="Estação de Live · YouTube"
      title="Live 24/7 no YouTube"
      subtitle="Playlist em loop infinito, overlay dinâmico e reconexão automática — a transmissão fica de pé por dias."
      warning="No YouTube Studio, crie a transmissão em 'Ao vivo → Transmitir agora', copie a chave RTMP e mantenha a live com latência normal. Recomendado: 1080p a 4500 kbps com GOP de 2s (já configurado nos presets)."
      keyHelp="Padrão do YouTube: rtmp://a.rtmp.youtube.com/live2"
    />
  );
}
