#!/usr/bin/env bash
# Ecossistema Viral — puxa a última versão do GitHub e aplica no aaPanel com segurança.
# Uso (um único comando no servidor):
#   cd /www/wwwroot/viral.vr766.com && bash deploy/safe-update.sh
#
# O que ele faz:
#   1. Aborta se houver alterações locais não commitadas (evita perda de trabalho).
#   2. Faz backup do .env e do storage de configurações.
#   3. Sincroniza com a branch remota do GitHub.
#   4. Restaura .env e permissões.
#   5. Executa deploy/update.sh (dependências + build + reinício).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${VIRAL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$APP_DIR"

log()  { printf '\n\033[1;35m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✔\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

BRANCH="${VIRAL_UPDATE_BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
REMOTE="${VIRAL_REMOTE:-origin}"

log "Modo seguro de atualização"
ok  "Diretório: $APP_DIR"
ok  "Branch:   $BRANCH"
ok  "Remote:   $REMOTE"

# --- 1. Verifica alterações locais não commitadas ---------------------------
if [ -n "$(git status --porcelain)" ]; then
  die "Há alterações locais não commitadas no aaPanel.\nCommit/push ou descarte antes de rodar este script.\nVeja: git status"
fi

# --- 2. Backup do .env e configs --------------------------------------------
if [ -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env" "$APP_DIR/.env.safe-update.bak"
  ok ".env salvo em .env.safe-update.bak"
fi

# --- 3. Fetch e sincronização forçada com o remoto --------------------------
log "Buscando novidades no GitHub ($REMOTE/$BRANCH)"
git fetch "$REMOTE" "$BRANCH" --prune

REMOTE_REF="$REMOTE/$BRANCH"
if ! git show-ref --verify --quiet "refs/remotes/$REMOTE_REF"; then
  die "Branch remota $REMOTE_REF não encontrada."
fi

LOCAL_REV="$(git rev-parse HEAD)"
REMOTE_REV="$(git rev-parse "$REMOTE_REF")"

if [ "$LOCAL_REV" = "$REMOTE_REV" ]; then
  ok "Código já está atualizado ($LOCAL_REV)"
else
  warn "Atualizando: $LOCAL_REV -> $REMOTE_REV"
  git reset --hard "$REMOTE_REF"
  ok "Código sincronizado com $REMOTE_REF"
fi

# --- 4. Restaura .env (o reset pode ter sobrescrito se .env estava no repo) ---
if [ -f "$APP_DIR/.env.safe-update.bak" ]; then
  mv "$APP_DIR/.env.safe-update.bak" "$APP_DIR/.env"
  ok ".env restaurado"
fi

# --- 5. Roda o update.sh padrão ---------------------------------------------
log "Aplicando dependências, build e reinício dos serviços"
bash "$APP_DIR/deploy/update.sh"

printf '\n\033[1;32m✔ Atualização segura concluída.\033[0].\033[0m\n'
