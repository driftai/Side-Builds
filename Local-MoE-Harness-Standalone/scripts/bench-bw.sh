#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT/.venvs/freetoken"

export PATH="$VENV_DIR/bin:$HOME/.local/bin:$PATH"
# shellcheck source=runtime-env-linux.sh
source "$ROOT/scripts/runtime-env-linux.sh"
local_moe_configure_cuda "$VENV_DIR/bin/python"
export XDG_CACHE_HOME="$ROOT/.cache"
export TORCH_EXTENSIONS_DIR="$ROOT/.cache/torch_extensions"

echo "[FreeToken] Running bandwidth benchmark -> caching in $XDG_CACHE_HOME/freetoken"
"$VENV_DIR/bin/ft" bench bw
