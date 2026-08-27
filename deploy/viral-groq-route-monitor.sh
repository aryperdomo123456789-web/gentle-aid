#!/usr/bin/env bash
# Monitor sanitizado de egress para api.groq.com.
# Não altera firewall, /etc/hosts ou credenciais; apenas testa e registra o estado.
set -u

APP_DIR="${VIRAL_ROOT:-/www/wwwroot/gentle-aid}"
ENV_FILE="$APP_DIR/.env"
HOST="api.groq.com"
ENDPOINT="https://${HOST}/openai/v1/models"
CONNECT_TIMEOUT="${GROQ_ROUTE_CONNECT_TIMEOUT:-5}"
MAX_TIME="${GROQ_ROUTE_MAX_TIME:-10}"

if [ -r "$ENV_FILE" ]; then
  set -a
  # O arquivo é controlado pelo deploy e nunca é impresso.
  . "$ENV_FILE"
  set +a
fi

log_line() {
  local line="$1"
  if command -v logger >/dev/null 2>&1; then
    logger -t viral-groq-route-monitor -- "$line" 2>/dev/null || true
  fi
  printf '%s\n' "$line"
}

if [ -z "${GROQ_API_KEY:-}" ]; then
  log_line "status=unconfigured host=${HOST} reason=GROQ_API_KEY_absent"
  exit 0
fi

mapfile -t ips < <(getent ahostsv4 "$HOST" 2>/dev/null | awk '{print $1}' | sort -u)
if [ "${#ips[@]}" -eq 0 ]; then
  log_line "status=unavailable host=${HOST} reason=dns_no_ipv4"
  exit 0
fi

for ip in "${ips[@]}"; do
  result="$(curl -4 --http1.1 --resolve "${HOST}:443:${ip}" -sS -o /dev/null \
    -w '%{http_code} %{time_total}' \
    --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
    -H "Authorization: Bearer ${GROQ_API_KEY}" \
    -H 'Accept: application/json' \
    -A 'EcossistemaViral/route-monitor' \
    "$ENDPOINT" 2>/dev/null || true)"
  code="${result%% *}"
  latency="${result#* }"
  if [ "$code" = "$result" ]; then
    latency="unknown"
  fi
  if [ "$code" = "200" ]; then
    log_line "status=reachable host=${HOST} ip=${ip} http_status=200 latency_seconds=${latency}"
    exit 0
  fi
  log_line "status=unavailable host=${HOST} ip=${ip} http_status=${code:-000} latency_seconds=${latency}"
done

exit 0
