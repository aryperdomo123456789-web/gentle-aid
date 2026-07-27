# Ecossistema Viral

Plataforma para criadores de conteúdo: download, clonagem, esterilização de
metadados e mutação estrutural de vídeos para bypass de algoritmo em TikTok,
Reels e Shorts.

- **Frontend:** React 19 + TanStack Start + Tailwind v4 (dark mode nativo).
- **Backend:** Flask em blueprints modulares + FFmpeg + yt-dlp.
- **Servidor:** aaPanel (Nginx reverse proxy → Gunicorn :8010 e Node :3010).

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
  install.sh                   instalação completa em um comando
  update.sh                    atualização após push no GitHub
  nginx-site.conf.template     config do site no aaPanel (renderizada)
  viral-api.service.template   systemd (Gunicorn)
  viral-web.service.template   systemd (Node/frontend)
  generated/                   arquivos renderizados p/ seu domínio (gitignored)
src/                      frontend React
```

Armazenamento em disco (caminho absoluto):

```
/www/wwwroot/viral.vr766.com/fabrica_clips/
  _uploads/  _jobs/  _youtube_jobs/  _tiktok_jobs/
  _legenda_jobs/  _voice_jobs/  _canva_jobs/
```

Cada job grava um JSON com status, log, metadados e hashes MD5 antes/depois.
Os downloads são servidos por rotas **relativas** (`/downloads/...`), atendidas
direto pelo Nginx via `alias` — sem CORS e sem caminho absoluto no HTML.

## Deploy no aaPanel (via GitHub) — 3 comandos

Pré-requisitos no painel: **Nginx**, **Node.js 20+** (App Store) e o site criado
com SSL. Depois, no terminal do servidor como root:

```bash
# 1. clonar dentro do diretório do site
cd /www/wwwroot/viral.vr766.com
git clone https://github.com/<seu-usuario>/<seu-repo>.git .

# 2. instalar TUDO (ffmpeg, .env, venv, deps, storage, build, systemd, nginx)
bash deploy/install.sh viral.vr766.com

# 3. colar no painel a config gerada em:
#    deploy/generated/nginx-viral.vr766.com.conf
#    (Site > viral.vr766.com > Arquivo de configuração — mantenha as linhas de SSL)
```

Teste final:

```bash
curl -s https://viral.vr766.com/api/health
```

O instalador é idempotente e faz sozinho: instala ffmpeg/python/git, gera `.env`
com `SECRET_KEY` aleatória, cria a venv, valida a importação do Flask, cria a
árvore `fabrica_clips/`, builda o frontend, registra e sobe `viral-api` e
`viral-web` no systemd, ativa o timer de auto-update, renderiza o Nginx para o
seu domínio e roda health check.

### Atualizar depois de um push no GitHub

```bash
cd /www/wwwroot/viral.vr766.com && bash deploy/update.sh
```

### Autoatualização

Depois do `deploy/install.sh`, o servidor passa a checar o GitHub em segundo
plano e aplica novos commits sozinho. Quando isso acontece, a aba aberta do
projeto detecta a nova versão e recarrega automaticamente.

Se quiser desativar temporariamente:

```bash
VIRAL_AUTO_UPDATE=0 systemctl restart viral-auto-update.timer
```

### Espelho automático de backup

O projeto também mantém um espelho automático no branch `backup`. Esse branch
recebe snapshots do estado atual do aaPanel em segundo plano, sem depender de
ação manual.

O timer faz uma checagem leve: se não houver diferença real no conteúdo, ele
sai sem criar commit nem travar o servidor.

Para desativar temporariamente:

```bash
VIRAL_BACKUP_MIRROR=0 systemctl restart viral-backup-mirror.timer
```

### Operação

```bash
systemctl status viral-api viral-web
journalctl -u viral-api -f     # logs da API/FFmpeg
journalctl -u viral-web -f     # logs do frontend
systemctl status viral-auto-update.timer viral-auto-update.service
systemctl restart viral-api viral-web
```

### Variáveis de ambiente

Geradas automaticamente em `.env` (referência completa em `.env.example`):

```
VIRAL_ROOT=/www/wwwroot/viral.vr766.com
VIRAL_STORAGE=/www/wwwroot/viral.vr766.com/fabrica_clips
SECRET_KEY=<aleatória>
MAX_UPLOAD_MB=1024
VIRAL_WORKERS=2
GUNICORN_BIND=127.0.0.1:8010
```

Chaves de provedores (OpenAI, DeepSeek, Groq, Tavily, ElevenLabs…) não precisam
ir no `.env`: cadastre pela aba **Central de APIs**, que grava no cofre
`fabrica_clips/_config/api_keys.json` (fora do Git). O autofill pesado no boot
fica desativado por padrão; se quiser reativá-lo, use
`VIRAL_AUTO_IMPORT_ON_BOOT=1`.

Se você tiver o TXT do legado com as chaves, pode importar tudo para o cofre
com:

```bash
python scripts/import_legacy_api_keys.py /caminho/para/TODASAPI.txt
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
