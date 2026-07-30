# Estação de Live 24/7 — duas ferramentas, duas páginas

Duas páginas separadas, mesmo motor por baixo:

- `/live-youtube` — **Live Loop YouTube** (RTMP libera na hora, sem gate)
- `/live-tiktok` — **Live Loop TikTok** (exige conta com acesso a stream key RTMP)

Tudo é desenvolvido e testado aqui no laboratório, mas o alvo é o GitHub → aaPanel, onde o FFmpeg roda de verdade.

## O que cada página faz

1. Escolher a fonte: um vídeo do acervo (histórico das outras ferramentas), upload direto, ou uma **playlist** de vários vídeos em fila.
2. Escolher o preset de qualidade (720p30 / 1080p30 / 1080p60) e o bitrate.
3. Overlay dinâmico opcional: relógio ao vivo, contador de tempo no ar, texto fixo. Isso evita que a plataforma leia a transmissão como "vídeo estático repetido".
4. Colar a URL RTMP + stream key (guardadas na Central de APIs, nunca no código).
5. Passar pela trava de confirmação (mesmo `JobSettingsGuard` das outras ferramentas) e dar START.
6. Painel ao vivo: uptime, bitrate real, frames enviados, frames dropados, tentativas de reconexão, log em tempo real e botão de kill.

O watchdog reconecta sozinho quando a plataforma derruba a sessão — é assim que se sustenta dias de transmissão.

## Detalhes técnicos

### Backend

- `backend/app/services/streamer.py` — motor único:
  - monta a playlist em `concat` com `-stream_loop -1 -re`
  - encoder: `libx264 -preset veryfast`, GOP fixo (`-g 2x fps`), `-c:a aac -b:a 128k -ar 44100`, saída `-f flv`
  - overlay via `drawtext` (relógio/contador) quando ligado
  - supervisiona o processo, faz parse do stderr do FFmpeg (`fps=`, `bitrate=`, `drop=`) e alimenta métricas
  - backoff exponencial na reconexão, teto de tentativas configurável
  - estado persistido em disco (`fabrica_clips/live/<id>.json`) para sobreviver a reciclagem de worker do Gunicorn
- `backend/app/blueprints/live.py` — `POST /api/live/start`, `POST /api/live/stop`, `GET /api/live/status`, `GET /api/live/sessions`, com `platform` = `youtube` | `tiktok`. Presets e validação de RTMP por plataforma ficam separados.
- Integração com `services/jobs.py`: cada sessão vira um job de longa duração rastreável, com log e timeline no padrão atual.
- Chaves: `YOUTUBE_RTMP_URL` / `YOUTUBE_STREAM_KEY` / `TIKTOK_RTMP_URL` / `TIKTOK_STREAM_KEY` na Central de APIs.

### Frontend

- `src/features/live/api.ts`, `types.ts`, `use-live-station.ts` (hook com polling de status)
- Componentes compartilhados: `SourcePicker`, `OverlayPanel`, `StreamHealth`, `LiveLog`
- `src/routes/live-youtube.tsx` e `src/routes/live-tiktok.tsx` — mesmas peças, cópias e avisos diferentes; `head()` próprio em cada rota
- Entrada no `TopNav`, layout `ToolShell` e responsivo como o resto do painel

### Deploy no aaPanel

- `deploy/viral-live.service.template` — systemd com `Restart=always`, para o motor sobreviver a reboot
- O install/update scripts passam a registrar o serviço
- Documentação em `docs/LIVE-247.md`: como pegar a stream key no YouTube Studio e no TikTok, e o que fazer quando a chave expira

## Laboratório aqui no Lovable

Antes de mandar pro GitHub eu valido com um `backend/lab/live_check.py`:

- gera mídia sintética longa, monta a playlist e o comando de encode
- transmite para um endpoint RTMP local de teste (ou `-f null`) e confere que o loop não corta na virada do arquivo
- força a queda da conexão e verifica que o watchdog reconecta com backoff
- confere que o parse de métricas (fps, bitrate, drop) bate com a saída real do FFmpeg

## Avisos que vão na tela

- **YouTube**: RTMP disponível pra qualquer conta verificada — funciona hoje.
- **TikTok**: stream key só aparece em contas com acesso a LIVE por software (normalmente 1.000+ seguidores). Sem isso a página avisa e não deixa iniciar.
- Loop puro sem interação é classificado como "low-quality LIVE". Por isso o overlay dinâmico vem ligado por padrão.
