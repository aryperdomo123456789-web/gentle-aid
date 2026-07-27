#!/usr/bin/env bash
# Ecossistema Viral — checagem automática de upgrades.
# Roda em background via systemd timer e aplica atualizações sem ação manual.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${VIRAL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

if [ "${VIRAL_AUTO_UPDATE:-1}" = "0" ]; then
  exit 0
fi

exec 9>"$APP_DIR/.viral-auto-update.lock"
flock -n 9 || exit 0

cd "$APP_DIR"

BRANCH="${VIRAL_UPDATE_BRANCH:-}"
if [ -z "$BRANCH" ]; then
  BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
fi
BRANCH="${BRANCH:-main}"

REMOTE_REF="origin/$BRANCH"

printf '\n\033[1;35m==>\033[0m Verificando atualizações automáticas (%s)\n' "$REMOTE_REF"
git fetch --all --prune --quiet
if ! git show-ref --verify --quiet "refs/remotes/$REMOTE_REF"; then
  REMOTE_REF="origin/main"
fi

LOCAL_REV="$(git rev-parse HEAD)"
REMOTE_REV="$(git rev-parse "$REMOTE_REF")"

if [ "$LOCAL_REV" = "$REMOTE_REV" ]; then
  printf '\033[1;32m  ✔\033[0m Nenhuma novidade no GitHub.\n'
  exit 0
fi

printf '\033[1;33m  !\033[0m Atualização detectada: %s -> %s\n' "$LOCAL_REV" "$REMOTE_REV"
bash "$APP_DIR/deploy/update.sh"
