# Ecossistema Viral

Plataforma para criadores de conteúdo: download, clonagem, esterilização de
metadados e mutação estrutural de vídeos para bypass de algoritmo em TikTok,
Reels e Shorts.

- **Frontend:** React 19 + TanStack Start + Tailwind v4 (dark mode nativo).
- **Backend:** Flask em blueprints modulares + FFmpeg + yt-dlp.
- **Servidor:** aaPanel (Nginx reverse proxy → Gunicorn :8000 e Node :3000).

## Ferramentas

| Rota | Ferramenta | Endpoint |
| --- | --- | --- |
| `/` | Download e Bypass Universal de YouTube | `POST /api/youtube/bypass` |
| `/tiktok` | TikTok Dashboard (radar + clonagem 1:1) | `GET /api/tiktok/trends`, `POST /api/tiktok/clone` |
| `/legendar` | Legendas dinâmicas queimadas | `POST /api/legendar/run` |
| `/voice-conversion` | Conversão de voz V2V | `POST /api/voice/convert` |
| `/canva-cleaner` | Recodificação e limpeza pós-Canva | `POST /api/canva-cleaner/run` |
| `/historico` | Central de histórico | `GET /api/jobs`, `GET /api/jobs/<id>` |

Todo job devolve `202` com o objeto do job; o frontend faz polling em
`GET /api/jobs/<id>` até `done`/`error` e mostra log, hashes MD5 e download.

## Estrutura

```
backend/
  wsgi.py                 entrypoint Gunicorn
  gunicorn.conf.py
  requirements.txt
  app/
    __init__.py           factory Flask
    config.py             caminhos absolutos, binários, limites
    blueprints/           youtube, tiktok, legendar, voice, canva_cleaner, jobs
    services/             jobs (fila + persistência), media (FFmpeg), validation
deploy/
  install.sh              instalação/atualização em um comando
  nginx-viralpro.conf     config do site no aaPanel
  viral-api.service       systemd (Gunicorn)
  viral-web.service       systemd (Node/frontend)
src/                      frontend React
```

Armazenamento em disco (caminho absoluto):

```
/www/wwwroot/viralpro.vr766.com/fabrica_clips/
  _uploads/  _jobs/  _youtube_jobs/  _tiktok_jobs/
  _legenda_jobs/  _voice_jobs/  _canva_jobs/
```

Cada job grava um JSON com status, log, metadados e hashes MD5 antes/depois.
Os downloads são servidos por rotas **relativas** (`/downloads/...`), atendidas
direto pelo Nginx via `alias` — sem CORS e sem caminho absoluto no HTML.

## Deploy no aaPanel (via GitHub)

```bash
# 1. no servidor, dentro do diretório do site
cd /www/wwwroot/viralpro.vr766.com
git clone https://github.com/<seu-usuario>/<seu-repo>.git .

# 2. instala tudo (ffmpeg, venv, deps, build do frontend, systemd)
bash deploy/install.sh

# 3. Nginx: cole deploy/nginx-viralpro.conf no config do site pelo painel
```

Atualizações depois disso:

```bash
cd /www/wwwroot/viralpro.vr766.com && git pull && bash deploy/install.sh
```

### Variáveis de ambiente (`.env` na raiz, opcional)

```
VIRAL_ROOT=/www/wwwroot/viralpro.vr766.com
SECRET_KEY=troque-isto
MAX_UPLOAD_MB=500
VIRAL_WORKERS=2
FFMPEG_BIN=ffmpeg
YTDLP_BIN=yt-dlp
```

## Desenvolvimento local

```bash
# backend
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
VIRAL_ROOT=$PWD/.local .venv/bin/python backend/wsgi.py   # :8000

# frontend (VITE_API_BASE=http://127.0.0.1:8000 no .env)
npm install && npm run dev
```

Sem a variável `VITE_API_BASE`, o frontend chama rotas relativas — o modo
correto em produção, onde Nginx serve frontend e API no mesmo domínio.
