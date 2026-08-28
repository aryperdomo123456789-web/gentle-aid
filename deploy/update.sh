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

printf '\n\033[1;35m==>\033[0m Removendo laboratórios do fluxo\n'
rm -f \
  src/routes/lab.tsx \
  src/routes/lab-legenda.tsx \
  src/lib/api-lab.server.ts \
  src/lib/api-lab.presets.ts \
  src/lib/api-lab.functions.ts \
  src/lib/caption-lab.ts

printf '\n\033[1;35m==>\033[0m Dependências Python\n'
"$APP_DIR/.venv/bin/pip" install -q -r backend/requirements.txt

printf '\n\033[1;35m==>\033[0m Migração explícita de billing/delivery\n'
bash "$APP_DIR/deploy/migrate-billing.sh" "$APP_DIR"

printf '\n\033[1;35m==>\033[0m Renderizando timers operacionais\n'
chmod 750 "$APP_DIR/deploy/viral-retention-gc.sh" 2>/dev/null || true
if command -v systemctl >/dev/null 2>&1; then
  RUN_USER="${VIRAL_USER:-www}"
  id -u "$RUN_USER" >/dev/null 2>&1 || RUN_USER="root"
  sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$RUN_USER|g" "$APP_DIR/deploy/viral-retention-gc.service.template" > /etc/systemd/system/viral-retention-gc.service
  sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$RUN_USER|g" "$APP_DIR/deploy/viral-retention-gc.timer.template" > /etc/systemd/system/viral-retention-gc.timer
  if [ -f "$APP_DIR/deploy/viral-groq-route-monitor.service.template" ]; then
    sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$RUN_USER|g" "$APP_DIR/deploy/viral-groq-route-monitor.service.template" > /etc/systemd/system/viral-groq-route-monitor.service
    sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$RUN_USER|g" "$APP_DIR/deploy/viral-groq-route-monitor.timer.template" > /etc/systemd/system/viral-groq-route-monitor.timer
  fi
  systemctl daemon-reload
  systemctl enable --now viral-retention-gc.timer viral-groq-route-monitor.timer >/dev/null 2>&1 || true
fi

printf '\n\033[1;35m==>\033[0m Build do frontend\n'
if command -v bun >/dev/null 2>&1 && { [ -f "$APP_DIR/bun.lock" ] || [ -f "$APP_DIR/bun.lockb" ]; }; then
  printf '\033[1;32m  ✔\033[0m Usando bun (bun.lock detectado)\n'
  bun install --frozen-lockfile || bun install
  NITRO_PRESET="${NITRO_PRESET:-node-server}" bun run build
elif [ -f "$APP_DIR/package-lock.json" ]; then
  npm ci --no-audit --no-fund || npm install --no-audit --no-fund
  NITRO_PRESET="${NITRO_PRESET:-node-server}" npm run build
else
  npm install --no-audit --no-fund
  NITRO_PRESET="${NITRO_PRESET:-node-server}" npm run build
fi

printf '\n\033[1;35m==>\033[0m Reiniciando serviços\n'
systemctl restart viral-api viral-web
if systemctl is-active --quiet viral-worker; then
  systemctl restart viral-worker
else
  printf '\033[1;33m  !\033[0m viral-worker não está ativo — execute a migração da fila e inicie-o quando autorizado.\n'
fi
sleep 3
curl -s http://127.0.0.1:"${VIRAL_API_PORT:-8010}"/api/health || true

printf '\n\033[1;35m==>\033[0m Espelhando estado atual no backup\n'
bash "$APP_DIR/deploy/backup-mirror.sh" || true

printf '\n\033[1;32m✔ Atualizado.\033[0m\n'
