#!/usr/bin/env bash
# Ecossistema Viral — atualização rápida depois de um push no GitHub.
#   cd /www/wwwroot/SEU_DOMINIO && bash deploy/update.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${VIRAL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$APP_DIR"

printf '\n\033[1;35m==>\033[0m Puxando código do GitHub\n'
git fetch --all --prune
git reset --hard "origin/$(git rev-parse --abbrev-ref HEAD)"

printf '\n\033[1;35m==>\033[0m Dependências Python\n'
"$APP_DIR/.venv/bin/pip" install -q -r backend/requirements.txt

printf '\n\033[1;35m==>\033[0m Build do frontend\n'
npm ci --no-audit --no-fund || npm install --no-audit --no-fund
npm run build

printf '\n\033[1;35m==>\033[0m Reiniciando serviços\n'
systemctl restart viral-api viral-web
sleep 3
curl -s http://127.0.0.1:"${VIRAL_API_PORT:-8000}"/api/health || true
printf '\n\033[1;32m✔ Atualizado.\033[0m\n'
