# Fluxo e Infra

## Mapa do fluxo

### 1) Lovable

O Lovable edita o codigo no repo conectado e faz push automatico para o GitHub.

### 2) GitHub

Repositorio atual vinculado:

- `git@github-gentle-aid:aryperdomo123456789-web/gentle-aid.git`

Repositorio legado citado no contexto:

- `https://github.com/aryperdomo123456789-web/viral`

### 3) aaPanel

Diretorio de deploy atual:

- `/www/wwwroot/gentle-aid`

Diretorio legado que confunde o fluxo:

- `/www/wwwroot/viral.vr766.com`

## Processos e portas

### Backend Flask / Gunicorn

- Servico: `viral-api`
- Working directory: `__APP_DIR__/backend`
- Porta padrao do Gunicorn: `127.0.0.1:8000`
- Referencias: `deploy/viral-api.service.template:9-14`, `backend/gunicorn.conf.py:1-10`

### Frontend TanStack Start / Node

- Servico: `viral-web`
- Porta definida por `PORT`
- Host local: `127.0.0.1`
- Referencias: `deploy/viral-web.service.template:9-14`

### Nginx

- `location /api/` faz proxy para a porta do Gunicorn
- `location /` faz proxy para o Node do frontend
- `location /downloads/` serve arquivos direto do storage
- Referencias: `deploy/nginx-site.conf.template:31-62`, `deploy/nginx-locations.conf.template:1-30`

## Variaveis criticas

- `VIRAL_ROOT`: raiz logica da aplicacao
- `VIRAL_STORAGE`: pasta de persistencia dos dados e dos jobs
- `VIRAL_FRONTEND`: saida do build do frontend
- `EnvironmentFile=-__APP_DIR__/.env`: o systemd carrega o `.env` do diretorio da aplicacao
- Referencias: `backend/app/config.py:7-31`, `deploy/viral-api.service.template:9-14`, `deploy/viral-web.service.template:9-14`

## Onde cada coisa fica

- Coefre de chaves: `fabrica_clips/_config/api_keys.json`
- Arquivo `.env`: `__APP_DIR__/.env`
- Build do frontend: `frontend_dist/`
- Uploads e jobs: `fabrica_clips/_uploads`, `fabrica_clips/_jobs`
- Referencias: `backend/app/services/api_keys.py:321-343`, `backend/app/services/api_keys.py:939-975`, `backend/app/config.py:31-56`

## Observacao de risco

O boot do backend chama `api_keys.autofill_once()` logo na criacao da app. Esse passo faz varredura em varios caminhos legados, inclusive:

- `config.app_root`
- `config.storage_dir / "_config"`
- `/www/wwwroot/viral.vr766.com`
- `/www/wwwroot/viral.vr766.com.bak`
- `/www/wwwroot/viral`
- `/root`

Referencia: `backend/app/services/api_keys.py:701-726`.

Esse desenho explica porque um problema de ambiente ou de filesystem pode se manifestar como "Carregando..." na tela, e nao como erro de dado vazio.

