#!/usr/bin/env bash
# =============================================================================
# Ecossistema Viral — instalação/atualização completa no aaPanel (1 comando).
#
#   cd /www/wwwroot/SEU_DOMINIO
#   bash deploy/install.sh seu.dominio.com
#
# Idempotente: rode de novo a cada `git pull` (ou use deploy/update.sh).
# Detecta sozinho o diretório do projeto, cria .env, venv, storage,
# builda o frontend, registra os serviços systemd e gera o Nginx pronto.
# =============================================================================
set -euo pipefail

log()  { printf '\n\033[1;35m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m  ✔\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
die()  { printf '\n\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

# --- 0. Contexto -------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${VIRAL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
DOMAIN="${1:-${VIRAL_DOMAIN:-$(basename "$APP_DIR")}}"
VENV="$APP_DIR/.venv"
STORAGE="${VIRAL_STORAGE:-$APP_DIR/fabrica_clips}"
API_PORT="${VIRAL_API_PORT:-8000}"
WEB_PORT="${VIRAL_WEB_PORT:-3000}"
RUN_USER="${VIRAL_USER:-www}"
id -u "$RUN_USER" >/dev/null 2>&1 || RUN_USER="root"

log "Projeto:  $APP_DIR"
ok  "Domínio:  $DOMAIN"
ok  "Usuário:  $RUN_USER   API :$API_PORT   Web :$WEB_PORT"
cd "$APP_DIR"

[ "$(id -u)" -eq 0 ] || warn "Sem root: systemd/nginx/pacotes podem falhar. Use 'sudo bash deploy/install.sh $DOMAIN'."

# --- 1. Dependências de sistema ---------------------------------------------
log "Dependências de sistema (ffmpeg, python3-venv, git)"
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v python3 >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y ffmpeg python3 python3-venv python3-pip git curl
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y epel-release || true
    dnf install -y ffmpeg python3 python3-pip git curl
  else
    yum install -y epel-release || true
    yum install -y ffmpeg python3 python3-pip git curl
  fi
fi
command -v ffmpeg  >/dev/null 2>&1 || die "ffmpeg não instalado — instale manualmente e rode de novo."
command -v ffprobe >/dev/null 2>&1 || die "ffprobe não instalado (vem no pacote ffmpeg)."
ok "$(ffmpeg -version | head -1)"

# --- 2. Arquivo .env ---------------------------------------------------------
log "Configuração (.env)"
if [ ! -f "$APP_DIR/.env" ]; then
  SECRET="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  cat > "$APP_DIR/.env" <<EOF
# Ecossistema Viral — gerado por deploy/install.sh
VIRAL_ROOT=$APP_DIR
VIRAL_STORAGE=$STORAGE
VIRAL_FRONTEND=$APP_DIR/frontend_dist
SECRET_KEY=$SECRET
MAX_UPLOAD_MB=1024
VIRAL_WORKERS=2
GUNICORN_BIND=127.0.0.1:$API_PORT
GUNICORN_WORKERS=2
GUNICORN_THREADS=8
LOG_LEVEL=info
FFMPEG_BIN=$(command -v ffmpeg)
FFPROBE_BIN=$(command -v ffprobe)
EOF
  ok ".env criado (SECRET_KEY aleatória)"
else
  ok ".env já existe — preservado"
fi
chmod 600 "$APP_DIR/.env" || true

# --- 3. Python ---------------------------------------------------------------
log "Ambiente virtual Python"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip wheel >/dev/null
"$VENV/bin/pip" install -r backend/requirements.txt
ok "$("$VENV/bin/python" -V)"

log "Verificando importação da API Flask"
( cd "$APP_DIR/backend" && VIRAL_ROOT="$APP_DIR" "$VENV/bin/python" -c "from app import create_app; create_app(); print('Flask OK')" ) \
  || die "A aplicação Flask não importou. Veja o erro acima."

# --- 4. Storage --------------------------------------------------------------
log "Estrutura de armazenamento"
mkdir -p "$STORAGE"/{_uploads,_jobs,_youtube_jobs,_tiktok_jobs,_legenda_jobs,_voice_jobs,_canva_jobs,_misc_jobs,_config}
chown -R "$RUN_USER":"$RUN_USER" "$STORAGE" 2>/dev/null || true
chmod -R 750 "$STORAGE" 2>/dev/null || true
ok "$STORAGE"

# --- 5. Frontend -------------------------------------------------------------
log "Frontend (Node)"
if command -v npm >/dev/null 2>&1; then
  NODE_MAJOR="$(node -v | sed 's/^v\([0-9]*\).*/\1/')"
  [ "${NODE_MAJOR:-0}" -ge 20 ] || warn "Node $(node -v) — recomendado Node 20+ (aaPanel > App Store > Node.js)."
  npm ci --no-audit --no-fund || npm install --no-audit --no-fund
  npm run build
  [ -f "$APP_DIR/.output/server/index.mjs" ] || die "Build do frontend não gerou .output/server/index.mjs"
  ok "Build concluído (.output/)"
else
  die "Node/npm não encontrado — instale pelo aaPanel (App Store > Node.js) e rode de novo."
fi

# --- 6. systemd --------------------------------------------------------------
log "Serviços systemd"
render() {
  sed -e "s|__APP_DIR__|$APP_DIR|g" \
      -e "s|__DOMAIN__|$DOMAIN|g" \
      -e "s|__USER__|$RUN_USER|g" \
      -e "s|__API_PORT__|$API_PORT|g" \
      -e "s|__WEB_PORT__|$WEB_PORT|g" \
      -e "s|__STORAGE__|$STORAGE|g" "$1"
}
if command -v systemctl >/dev/null 2>&1; then
  render "$SCRIPT_DIR/viral-api.service.template" > /etc/systemd/system/viral-api.service
  render "$SCRIPT_DIR/viral-web.service.template" > /etc/systemd/system/viral-web.service
  systemctl daemon-reload
  systemctl enable viral-api viral-web >/dev/null 2>&1 || true
  systemctl restart viral-api viral-web
  ok "viral-api e viral-web ativos"
else
  warn "systemctl indisponível — inicie manualmente os serviços."
fi

# --- 7. Nginx ----------------------------------------------------------------
log "Configuração Nginx"
mkdir -p "$SCRIPT_DIR/generated"
NGINX_OUT="$SCRIPT_DIR/generated/nginx-$DOMAIN.conf"
render "$SCRIPT_DIR/nginx-site.conf.template" > "$NGINX_OUT"
ok "Gerado: $NGINX_OUT"

# --- 8. Health check ---------------------------------------------------------
log "Health check da API"
HEALTH=""
for _ in $(seq 1 20); do
  HEALTH="$(curl -s "http://127.0.0.1:$API_PORT/api/health" || true)"
  [ -n "$HEALTH" ] && break
  sleep 1
done
if [ -n "$HEALTH" ]; then ok "API: $HEALTH"; else warn "API não respondeu — veja: journalctl -u viral-api -n 50"; fi

WEB_CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$WEB_PORT/" || true)"
[ "$WEB_CODE" = "200" ] && ok "Frontend respondendo na :$WEB_PORT" || warn "Frontend HTTP $WEB_CODE — veja: journalctl -u viral-web -n 50"

cat <<MSG

============================================================
✅ Ecossistema Viral instalado em $APP_DIR

Último passo (uma vez só), no aaPanel:
  Site > $DOMAIN > Arquivo de configuração
  -> cole o conteúdo de:
     $NGINX_OUT
  -> mantenha as linhas de SSL geradas pelo aaPanel e salve
  -> Nginx: reiniciar

Testes:
  curl -s https://$DOMAIN/api/health
  https://$DOMAIN/

Atualizar depois de um push no GitHub:
  cd $APP_DIR && bash deploy/update.sh

Logs:
  journalctl -u viral-api -f
  journalctl -u viral-web -f
============================================================
MSG
