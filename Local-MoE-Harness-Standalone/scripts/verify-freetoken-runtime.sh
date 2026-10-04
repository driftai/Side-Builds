#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || true)"
fi
if [[ -z "$PYTHON" ]]; then
  echo "[FreeToken Verify] ERROR: python3 is required to verify the runtime contract." >&2
  exit 1
fi

exec "$PYTHON" "$ROOT/scripts/freetoken_patch_contract.py" verify "$@"
