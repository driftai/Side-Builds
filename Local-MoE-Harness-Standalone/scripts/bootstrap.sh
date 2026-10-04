#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
FREETOKEN_REPO="https://github.com/FlashML-org/FreeToken.git"
FREETOKEN_SHA="0ab982f10905fa775962a4eddcb44caa50065251"
CUDA_TOOLKIT_VERSION="13.0.2"
CUDA_NVVM_VERSION="13.0.88"
FLASHINFER_VERSION="0.6.18.post1"
RUNTIME_DIR="$ROOT/runtime/freetoken"
FT_VENV="$ROOT/.venvs/freetoken"

mkdir -p "$ROOT/.cache/pip" "$ROOT/.cache/uv" "$ROOT/.tmp" "$ROOT/models/hf_cache" "$ROOT/logs" "$ROOT/state" "$ROOT/runtime" "$ROOT/.venvs"
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

for tool in python3 git; do command -v "$tool" >/dev/null 2>&1 || { echo "[Setup] ERROR: required tool not found: $tool" >&2; exit 1; }; done

echo "[Local MoE Harness] Linux/WSL self-contained bootstrap"
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/requirements.txt"

if [[ ! -d "$RUNTIME_DIR/.git" ]]; then
  if [[ -e "$RUNTIME_DIR" ]]; then
    echo "[Setup] ERROR: $RUNTIME_DIR exists but is not a FreeToken Git checkout." >&2
    echo "[Setup] Refusing to delete or overwrite it automatically." >&2
    exit 1
  fi
  git clone "$FREETOKEN_REPO" "$RUNTIME_DIR"
fi
CURRENT_SHA="$(git -C "$RUNTIME_DIR" rev-parse HEAD)"
if [[ "$CURRENT_SHA" != "$FREETOKEN_SHA" ]]; then
  if [[ -n "$(git -C "$RUNTIME_DIR" status --porcelain)" ]]; then
    echo "[Setup] ERROR: existing FreeToken runtime has local changes at $CURRENT_SHA." >&2
    echo "[Setup] Refusing to reset project-owned runtime automatically." >&2
    exit 1
  fi
  git -C "$RUNTIME_DIR" fetch --tags origin
  git -C "$RUNTIME_DIR" checkout --detach "$FREETOKEN_SHA"
fi

python3 -m venv "$FT_VENV"
"$FT_VENV/bin/python" -m pip install --upgrade pip "setuptools<82" wheel
# PyTorch 2.11 and current FreeToken use CUDA 13. Keep the matching compiler,
# headers and runtime inside the FreeToken venv so setup does not depend on or
# modify a system CUDA toolkit. Pin NVVM explicitly because the nvcc package's
# dependency is otherwise unconstrained across CUDA 13 minor releases.
"$FT_VENV/bin/python" -m pip install \
  "cuda-toolkit[cccl,crt,cudart,nvcc]==$CUDA_TOOLKIT_VERSION" \
  "nvidia-nvvm==$CUDA_NVVM_VERSION"
# shellcheck source=runtime-env-linux.sh
source "$ROOT/scripts/runtime-env-linux.sh"
local_moe_configure_cuda "$FT_VENV/bin/python"
"$FT_VENV/bin/python" -m pip install \
  --extra-index-url https://download.pytorch.org/whl/cu130 \
  --extra-index-url https://docs.sglang.io/whl/cu130 \
  --extra-index-url https://flashinfer.ai/whl \
  --extra-index-url https://flashinfer.ai/whl/cu130 \
  -e "$RUNTIME_DIR[accel]" \
  "flashinfer-python[cu13]==$FLASHINFER_VERSION" \
  "flashinfer-cubin==$FLASHINFER_VERSION" \
  "flashinfer-jit-cache==$FLASHINFER_VERSION+cu130"

"$ROOT/.venv/bin/python" "$ROOT/scripts/freetoken_patch_contract.py" apply --verbose
"$ROOT/.venv/bin/python" "$ROOT/scripts/freetoken_patch_contract.py" verify --verbose

echo
if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true; else echo "[Setup] Warning: nvidia-smi is not available; FreeToken requires an NVIDIA CUDA-capable GPU."; fi
echo "[Setup] READY"
echo "  Harness venv:   $ROOT/.venv"
echo "  FreeToken venv: $FT_VENV"
echo "  CUDA toolkit:   $CUDA_HOME"
echo "  FreeToken src:  $RUNTIME_DIR"
echo "  Models/cache:   $ROOT/models / $ROOT/.cache"
echo "No model weights were downloaded automatically."
