#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/www/wwwroot/gentle-aid}"
PYTHON="$APP_DIR/.venv/bin/python"
export VIRAL_ROOT="$APP_DIR"
export VIRAL_STORAGE="${VIRAL_STORAGE:-$APP_DIR/fabrica_clips}"
export PYTHONPATH="$APP_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON" - <<'PY'
from app.services import retention

result = retention.collect(limit=500)
print("retention_gc scanned={scanned} expired={expired} files_removed={files_removed}".format(**result))
PY
