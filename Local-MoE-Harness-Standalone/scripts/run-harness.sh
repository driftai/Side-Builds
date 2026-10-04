#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .venv ]]; then echo "Missing .venv. Run ./scripts/bootstrap.sh first."; exit 1; fi
mkdir -p "$ROOT/.cache" "$ROOT/.tmp" "$ROOT/models/hf_cache" "$ROOT/logs" "$ROOT/state"
export PIP_CACHE_DIR="$ROOT/.cache/pip"
export XDG_CACHE_HOME="$ROOT/.cache"
export HF_HOME="$ROOT/models/hf_cache"
export HUGGINGFACE_HUB_CACHE="$ROOT/models/hf_cache/hub"
export TORCH_HOME="$ROOT/.cache/torch"
export TRITON_CACHE_DIR="$ROOT/.cache/triton"
export FLASHINFER_WORKSPACE_DIR="$ROOT/.cache/flashinfer"
export TORCH_EXTENSIONS_DIR="$ROOT/.cache/torch_extensions"
export FREETOKEN_HOME="$ROOT/.freetoken"
export TMPDIR="$ROOT/.tmp"
source .venv/bin/activate
HOST=$(python - <<'PY'
from app.config import load_settings
print(load_settings()["harness_host"])
PY
)
PORT=$(python - <<'PY'
from app.config import load_settings
print(load_settings()["harness_port"])
PY
)
RELOAD_ARGS=()
if [[ "${HARNESS_RELOAD:-0}" == "1" ]]; then RELOAD_ARGS=(--reload); fi
echo "[Local MoE Harness] Starting harness backend at http://$HOST:$PORT"
exec uvicorn app.main:app --host "$HOST" --port "$PORT" "${RELOAD_ARGS[@]}"
