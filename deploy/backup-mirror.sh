#!/usr/bin/env bash
# Espelho automático do estado atual do aaPanel para o branch de backup.
# O fluxo é leve: se nada mudou, ele sai sem gerar commit nem push.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${VIRAL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
BRANCH="${VIRAL_BACKUP_BRANCH:-backup}"

if [ "${VIRAL_BACKUP_MIRROR:-1}" = "0" ]; then
  exit 0
fi

exec 9>"$APP_DIR/.viral-backup-mirror.lock"
flock -n 9 || exit 0

cd "$APP_DIR"

printf '\n\033[1;35m==>\033[0m Espelho automático para o branch %s\n' "$BRANCH"

# Atualiza a referência remota sem bloquear o fluxo principal.
git fetch origin "$BRANCH" --prune --quiet || git fetch origin --prune --quiet

REMOTE_REF="refs/remotes/origin/$BRANCH"
REMOTE_COMMIT="$(git rev-parse --verify --quiet "$REMOTE_REF" || true)"

# Captura o estado atual do diretório, sem incluir conteúdo ignorado.
git add -A -- .
TREE="$(git write-tree)"

if [ -n "$REMOTE_COMMIT" ]; then
  REMOTE_TREE="$(git rev-parse "$REMOTE_COMMIT^{tree}")"
  if [ "$TREE" = "$REMOTE_TREE" ]; then
    printf '\033[1;32m  ✔\033[0m Nenhuma diferença para espelhar.\n'
    exit 0
  fi
  PARENT="$REMOTE_COMMIT"
else
  PARENT="$(git rev-parse HEAD)"
fi

MESSAGE="mirror: snapshot aaPanel $(date -u +%Y-%m-%dT%H:%M:%SZ)"
NEW_COMMIT="$(
  printf '%s\n' "$MESSAGE" | \
    GIT_AUTHOR_NAME="Viral Mirror" \
    GIT_AUTHOR_EMAIL="mirror@viral.local" \
    GIT_COMMITTER_NAME="Viral Mirror" \
    GIT_COMMITTER_EMAIL="mirror@viral.local" \
    git commit-tree "$TREE" -p "$PARENT"
)"

git push origin "$NEW_COMMIT:refs/heads/$BRANCH" --quiet
printf '\033[1;32m  ✔\033[0m Backup atualizado em %s\n' "$BRANCH"
