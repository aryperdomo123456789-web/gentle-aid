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
      guideTitle="Passo a passo — TikTok LIVE"
      steps={[
        {
          title: "Confirme o acesso a LIVE por software",
          detail:
            "É preciso ter 1.000+ seguidores e conta com 18+. No app, o botão LIVE aparece em '+' → LIVE. Sem esse acesso o TikTok não gera chave RTMP.",
        },
        {
          title: "Abra o LIVE Studio ou o LIVE Center",
          detail:
            "No desktop: livecenter.tiktok.com → 'Go LIVE'. No app: '+' → LIVE → ícone de configurações → 'Transmitir com software/OBS'.",
        },
        {
          title: "Crie a sessão com título e categoria",
          detail:
            "Defina título, tópico e capa antes de gerar a chave. Essas informações não podem ser alteradas depois que a live começar.",
        },
        {
          title: "Gere a URL e a chave de stream",
          detail:
            "Clique em 'Iniciar transmissão / Gerar chave'. A URL costuma ser rtmp://push.tiktokcdn.com/live/ e a chave é única — ela expira e muda a cada nova live.",
        },
        {
          title: "Cole os dois campos aqui imediatamente",
          detail:
            "Preencha 'URL RTMP' e 'Stream key' abaixo. Como a chave do TikTok é descartável, não vale a pena salvar na Central de APIs — só a URL base.",
        },
        {
          title: "Selecione vídeos verticais 9:16",
          detail:
            "Marque os arquivos da biblioteca ou envie do PC. Conteúdo horizontal entra com barras pretas — prefira 1080x1920 para ocupar a tela inteira.",
        },
        {
          title: "Use o preset vertical",
          detail:
            "'Vertical 720x1280 · 30 fps' é o mais estável para o TikTok. Suba para 1080x1920 apenas se o servidor tiver folga de CPU.",
        },
        {
          title: "Mantenha o overlay ligado",
          detail:
            "Relógio e contador mudam o frame a cada segundo, reduzindo o risco de bloqueio por conteúdo repetido em loop.",
        },
        {
          title: "Confirme as configurações e entre ao vivo",
          detail:
            "Salve as configurações e clique em 'Entrar ao vivo'. Assim que o painel mostrar fps e bitrate, volte ao TikTok e confirme 'Go LIVE'.",
        },
        {
          title: "Acompanhe e encerre pelo painel",
          detail:
            "O watchdog reconecta sozinho em quedas. Ao finalizar, clique em 'Encerrar transmissão' aqui e encerre a live no TikTok — a próxima exigirá uma chave nova.",
        },
      ]}
    />
  );
}

