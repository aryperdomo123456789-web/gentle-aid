#!/usr/bin/env bash
# Aplica o proxy do Ecossistema Viral no site do aaPanel, sem mexer no SSL.
# Uso: bash deploy/apply-nginx.sh viral.vr766.com [API_PORT] [WEB_PORT]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOMAIN="${1:-${VIRAL_DOMAIN:-}}"
API_PORT="${2:-${VIRAL_API_PORT:-8010}}"
WEB_PORT="${3:-${VIRAL_WEB_PORT:-3010}}"
STORAGE="${VIRAL_STORAGE:-$APP_DIR/fabrica_clips}"

log() { printf '\n\033[1;35m▶ %s\033[0m\n' "$*"; }
ok()  { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
die() { printf '  \033[0;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[ -n "$DOMAIN" ] || die "Informe o domínio: bash deploy/apply-nginx.sh viral.vr766.com"

SITE_CONF="/www/server/panel/vhost/nginx/$DOMAIN.conf"
[ -f "$SITE_CONF" ] || die "Site não encontrado no aaPanel: $SITE_CONF (crie o site no painel primeiro)"

SNIPPET_DIR="$APP_DIR/deploy/generated"
SNIPPET="$SNIPPET_DIR/$DOMAIN.locations.conf"
mkdir -p "$SNIPPET_DIR"

log "Gerando trecho de proxy (API :$API_PORT / Web :$WEB_PORT)"
sed -e "s|__API_PORT__|$API_PORT|g" \
    -e "s|__WEB_PORT__|$WEB_PORT|g" \
    -e "s|__STORAGE__|$STORAGE|g" \
    "$SCRIPT_DIR/nginx-locations.conf.template" > "$SNIPPET"
ok "$SNIPPET"

BACKUP="$SITE_CONF.viral-bak.$(date +%Y%m%d%H%M%S)"
cp "$SITE_CONF" "$BACKUP"
ok "Backup: $BACKUP"

log "Ajustando o site do aaPanel"
python3 - "$SITE_CONF" "$SNIPPET" <<'PY'
import re, sys
conf_path, snippet = sys.argv[1], sys.argv[2]
src = open(conf_path, encoding='utf-8', errors='surrogateescape').read()

BEGIN = "    # >>> VIRAL PROXY BEGIN (gerado por deploy/apply-nginx.sh) >>>"
END   = "    # <<< VIRAL PROXY END <<<"
block = f"{BEGIN}\n    include {snippet};\n{END}\n"

# remove bloco anterior, se existir
src = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "", src, flags=re.S)

# comenta diretivas que o nosso trecho redefine (evita "directive is duplicate")
DUPES = re.compile(r'^\s*(client_max_body_size|client_body_timeout|proxy_read_timeout|proxy_send_timeout|send_timeout)\s')
src = "\n".join(
    ("    # [viral] " + l.strip()) if DUPES.match(l) else l
    for l in src.split("\n")
)

# comenta 'location /', regras estáticas por extensão e includes do aaPanel que
# roubam os assets (.js/.css) do frontend Node
STEAL = (
    re.compile(r'^location\s+/\s*\{'),
    re.compile(r'^location\s+[~^=][^\{]*\{'),
)
INCLUDES = re.compile(r'^\s*include\s+.*(enable-php|rewrite/|pathinfo)', re.I)

lines, out, depth, commenting = src.split("\n"), [], 0, False
for line in lines:
    stripped = line.strip()
    if not commenting and any(p.match(stripped) for p in STEAL):
        commenting, depth = True, 0
    if commenting:
        depth += line.count("{") - line.count("}")
        out.append("    # [viral] " + line.strip())
        if depth <= 0:
            commenting = False
        continue
    if INCLUDES.match(line):
        out.append("    # [viral] " + stripped)
        continue
    out.append(line)
src = "\n".join(out)

# injeta o include logo após a abertura do primeiro server { que tenha o domínio
idx = src.find("server")
pos = src.find("{", idx)
src = src[:pos + 1] + "\n" + block + src[pos + 1:]

open(conf_path, "w", encoding='utf-8', errors='surrogateescape').write(src)
print("include injetado")
PY

log "Testando configuração do Nginx"
nginx -t || die "nginx -t falhou. Restaure com: cp $BACKUP $SITE_CONF"
nginx -s reload || systemctl reload nginx
ok "Nginx recarregado — teste: https://$DOMAIN/"
