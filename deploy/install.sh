#!/usr/bin/env bash
# Ecossistema Viral — instalação/atualização no aaPanel em um comando.
#
#   bash deploy/install.sh
#
# Idempotente: pode ser rodado de novo a cada `git pull`.
set -euo pipefail

APP_DIR="${VIRAL_ROOT:-/www/wwwroot/viralpro.vr766.com}"
VENV="$APP_DIR/.venv"
STORAGE="$APP_DIR/fabrica_clips"

echo "==> Diretório da aplicação: $APP_DIR"
cd "$APP_DIR"

echo "==> Dependências de sistema (ffmpeg)"
if ! command -v ffmpeg >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y && apt-get install -y ffmpeg
  else
    yum install -y epel-release && yum install -y ffmpeg
  fi
fi
ffmpeg -version | head -1

echo "==> Ambiente virtual Python"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip wheel >/dev/null
"$VENV/bin/pip" install -r backend/requirements.txt

echo "==> Estrutura de armazenamento"
mkdir -p "$STORAGE"/{_uploads,_jobs,_youtube_jobs,_tiktok_jobs,_legenda_jobs,_voice_jobs,_canva_jobs}
chown -R www:www "$STORAGE" 2>/dev/null || true

echo "==> Frontend (Node)"
if command -v npm >/dev/null 2>&1; then
  npm ci --no-audit --no-fund || npm install --no-audit --no-fund
  npm run build
else
  echo "!! Node/npm não encontrado — instale pelo aaPanel (App Store > Node.js)."
fi

echo "==> Serviços systemd"
install -m 644 deploy/viral-api.service /etc/systemd/system/viral-api.service
install -m 644 deploy/viral-web.service /etc/systemd/system/viral-web.service
systemctl daemon-reload
systemctl enable --now viral-api viral-web
systemctl restart viral-api viral-web

echo "==> Status"
systemctl --no-pager --lines=5 status viral-api || true
systemctl --no-pager --lines=5 status viral-web || true

cat <<'MSG'

✅ Instalação concluída.

Falta apenas configurar o Nginx do site no aaPanel:
  Site > viralpro.vr766.com > Arquivo de configuração
  -> cole o conteúdo de deploy/nginx-viralpro.conf (mantendo as linhas de SSL)
  -> salve e reinicie o Nginx

Teste: curl -s https://viralpro.vr766.com/api/health
MSG
