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
      guideTitle="Passo a passo — YouTube Live"
      steps={[
        {
          title: "Libere o recurso de live no canal",
          detail:
            "Em youtube.com/verify confirme o telefone. A primeira ativação de transmissão leva até 24 h — faça isso um dia antes.",
        },
        {
          title: "Crie a transmissão no YouTube Studio",
          detail:
            "Studio → Criar (ícone de câmera) → 'Transmitir ao vivo' → aba 'Transmitir agora'. Defina título, privacidade e se é conteúdo para crianças.",
        },
        {
          title: "Ajuste a latência para Normal",
          detail:
            "Em 'Configurações de transmissão' escolha latência Normal. É a opção mais tolerante a oscilação de rede e a que melhor combina com loop 24/7.",
        },
        {
          title: "Copie a URL e a chave RTMP",
          detail:
            "Na mesma tela: URL do servidor (rtmp://a.rtmp.youtube.com/live2) e 'Chave de transmissão'. Clique em revelar e copie. Ela é permanente — dá para salvar e reutilizar.",
        },
        {
          title: "Cole aqui e guarde na Central de APIs",
          detail:
            "Preencha os campos 'URL RTMP' e 'Stream key' abaixo. Salvando na Central de APIs, nas próximas lives o campo pode ficar em branco.",
        },
        {
          title: "Monte a playlist",
          detail:
            "Marque os vídeos da biblioteca ou envie do PC. Vários arquivos tocam em sequência e o conjunto todo repete em loop infinito.",
        },
        {
          title: "Escolha o preset e o overlay",
          detail:
            "1080p · 30 fps (4500 kbps) é o equilíbrio ideal. Deixe relógio e contador ligados: o frame em movimento evita o alerta de vídeo estático repetido.",
        },
        {
          title: "Confirme as configurações e entre ao vivo",
          detail:
            "Clique em salvar configurações e depois em 'Entrar ao vivo'. Em poucos segundos o painel de saúde mostra fps, bitrate e frames enviados.",
        },
        {
          title: "Volte ao Studio e clique em 'Transmitir ao vivo'",
          detail:
            "Quando o YouTube detectar o sinal, o preview aparece e o botão fica verde. Só então a live vai ao ar publicamente.",
        },
        {
          title: "Deixe rodando",
          detail:
            "O watchdog reconecta sozinho com backoff se o RTMP cair. Para encerrar, use 'Encerrar transmissão' aqui e depois finalize a live no Studio.",
        },
      ]}
    />
  );
}

