#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/www/wwwroot/gentle-aid}"
PYTHON="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python do aplicativo não encontrado: $PYTHON" >&2
  exit 1
fi

cd "$APP_DIR"
export VIRAL_ROOT="$APP_DIR"
export VIRAL_STORAGE="${VIRAL_STORAGE:-$APP_DIR/fabrica_clips}"
export PYTHONPATH="$APP_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" - <<'PY'
from app.services import billing, release_keys, webhook_delivery

release_keys.migrate()
billing.migrate()
webhook_delivery.migrate()
print("billing_migration=ok")
PY
