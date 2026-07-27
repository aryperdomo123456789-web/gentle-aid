#!/usr/bin/env python3
"""Importa chaves do documento legado de APIs para o cofre local.

Uso:
  python scripts/import_legacy_api_keys.py /caminho/para/TODASAPI.txt

O script lê o TXT legado, usa o importador existente do backend e grava as
chaves em `fabrica_clips/_config/api_keys.json`. Nenhuma chave é impressa.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python scripts/import_legacy_api_keys.py /caminho/para/TODASAPI.txt", file=sys.stderr)
        return 2

    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.exists():
        print(f"Arquivo não encontrado: {source}", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    backend_root = repo_root / "backend"
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app.services import api_keys

    text = source.read_text(encoding="utf-8", errors="ignore")
    parsed = api_keys._parse_legacy_catalog(text)  # type: ignore[attr-defined]
    if not parsed:
        print("Nenhuma chave reconhecida no documento legado.", file=sys.stderr)
        return 1

    imported: list[str] = []
    for provider_id, key in parsed.items():
        if provider_id not in api_keys.PROVIDER_BY_ID:
            continue
        api_keys.set_key(provider_id, key, note=f"Importado de {source.name}")
        imported.append(provider_id)

    print(f"Importadas {len(imported)} chaves de {source.name}.")
    if imported:
        print(f"Provedores: {', '.join(imported)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
