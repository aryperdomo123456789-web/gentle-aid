#!/usr/bin/env bash
# Migração deliberadamente separada do boot/deploy.
# Uso somente após revisão:
#   CONFIRM=APPLY_API_V1_MIGRATION bash deploy/migrate-api-v1.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${VIRAL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
ENV_FILE="$APP_DIR/.env"

if [[ "${CONFIRM:-}" != "APPLY_API_V1_MIGRATION" ]]; then
  printf '%s\n' "Migração bloqueada. Revise o diff e use CONFIRM=APPLY_API_V1_MIGRATION para autorizar." >&2
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  printf '%s\n' "Arquivo .env ausente: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

PYTHON="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

cd "$APP_DIR/backend"
VIRAL_ROOT="$APP_DIR" "$PYTHON" - <<'PY'
from app.services import idempotency

idempotency.migrate()
print("api_idempotency migration applied")
PY
