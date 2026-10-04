#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VENV_DIR="$ROOT/.venvs/freetoken"
RUNTIME_DIR="$ROOT/runtime/freetoken"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "FreeToken venv not found at $VENV_DIR"
  exit 1
fi

export PATH="$VENV_DIR/bin:$HOME/.local/bin:$PATH"
# Use the same project-local CUDA 13 compiler/runtime that built FreeToken.
# shellcheck source=runtime-env-linux.sh
source "$ROOT/scripts/runtime-env-linux.sh"
local_moe_configure_cuda "$VENV_DIR/bin/python"
# Do NOT force FREETOKEN_CPU_MOE_FLAG_SYNC=0 here. FreeToken's default flag-based
# CUDA<->CPU handshake is faster when stream memory operations are supported, and
# FreeToken already falls back automatically when the driver cannot use it.
export HF_HOME="$ROOT/models/hf_cache"
export HF_HUB_ENABLE_HF_TRANSFER=1
export HF_XET_HIGH_PERFORMANCE=1
export XDG_CACHE_HOME="$ROOT/.cache"
export FLASHINFER_WORKSPACE_DIR="$ROOT/.cache/flashinfer"
export TORCH_EXTENSIONS_DIR="$ROOT/.cache/torch_extensions"
mkdir -p "$HF_HOME" "$XDG_CACHE_HOME/freetoken" "$FLASHINFER_WORKSPACE_DIR" "$TORCH_EXTENSIONS_DIR"

# Pin FreeToken to this project's measured hardware profile instead of relying on
# discovery. The pinned FreeToken revision honors FREETOKEN_BENCHBW_PATH.
BENCHBW_PROFILE="$XDG_CACHE_HOME/freetoken/benchbw.json"
if [[ -f "$BENCHBW_PROFILE" ]]; then
  export FREETOKEN_BENCHBW_PATH="$BENCHBW_PROFILE"
fi

MODEL="${1:-nvidia/Qwen3.6-35B-A3B-NVFP4}"
if [[ "$MODEL" == "Qwen/Qwen3.6-35B-A3B-NVFP4" ]]; then
  MODEL="nvidia/Qwen3.6-35B-A3B-NVFP4"
fi

# Prefer local self-contained FTW checkpoint if available.
if [[ -d "$ROOT/models/ftw/${MODEL##*/}" ]]; then
  MODEL="$ROOT/models/ftw/${MODEL##*/}"
elif [[ -d "$ROOT/models/ftw/$MODEL" ]]; then
  MODEL="$ROOT/models/ftw/$MODEL"
elif [[ -d "$ROOT/models/$MODEL" ]]; then
  MODEL="$ROOT/models/$MODEL"
fi

# The pinned native GGUF path JIT-compiles CUDA kernels on first generation.
# CUDA 12.8 rejects this distro's default GCC 13, while the installed GCC 12
# toolchain is supported. Use FreeToken's own override only for GGUF launches so
# existing safetensors/FTW model toolchains remain untouched.
if [[ "$MODEL" == *.gguf && -z "${FREETOKEN_GGUF_HOST_CXX:-}" ]]; then
  GGUF_HOST_CXX="$(command -v g++-12 || true)"
  if [[ -n "$GGUF_HOST_CXX" ]]; then
    export FREETOKEN_GGUF_HOST_CXX="$GGUF_HOST_CXX"
  fi
fi
PORT="${2:-1919}"
SERVED_MODEL_NAME="${LOCAL_MOE_SERVED_MODEL_NAME:-$MODEL}"
shift 2 2>/dev/null || shift $# 2>/dev/null || true

MEMORY_RATIO="${LOCAL_MOE_MEMORY_RATIO:-0.92}"
KV_RESERVE_TOKENS="${LOCAL_MOE_KV_RESERVE_TOKENS:-12288}"
MAX_PREFILL_LENGTH="${LOCAL_MOE_MAX_PREFILL_LENGTH:-2048}"
MAX_RUNNING_REQUESTS="${LOCAL_MOE_MAX_RUNNING_REQUESTS:-1}"
MOE_PREFILL_HIT_D2D="${LOCAL_MOE_PREFILL_HIT_D2D:-1}"

CUDA_GRAPH_MAX_BS="${LOCAL_MOE_CUDA_GRAPH_MAX_BS:-1}"
MOE_CACHE_SIZE="${LOCAL_MOE_MOE_CACHE_SIZE:-}"

# Recovery uses the selected registry model's conservative geometry. For the
# default Qwen model this remains the verified 4K profile; alternates may use a
# smaller model-specific fallback.
if [[ "${LOCAL_MOE_RECOVERY:-0}" == "1" ]]; then
  MEMORY_RATIO="${LOCAL_MOE_RECOVERY_MEMORY_RATIO:-0.90}"
  KV_RESERVE_TOKENS="${LOCAL_MOE_RECOVERY_KV_RESERVE_TOKENS:-4096}"
  MAX_PREFILL_LENGTH="${LOCAL_MOE_RECOVERY_MAX_PREFILL_LENGTH:-1024}"
  MOE_PREFILL_HIT_D2D="${LOCAL_MOE_RECOVERY_PREFILL_HIT_D2D:-0}"
fi

PREFILL_ARGS=()
if [[ "$MOE_PREFILL_HIT_D2D" == "1" ]]; then
  PREFILL_ARGS+=(--moe-prefill-hit-d2d)
fi

EXTRA_SERVE_ARGS=()
if [[ -n "$MOE_CACHE_SIZE" ]]; then
  EXTRA_SERVE_ARGS+=(--moe-cache-size "$MOE_CACHE_SIZE")
fi

echo "[FreeToken] Launching FreeToken server from self-contained root:"
echo "  Project ROOT: $ROOT"
echo "  Venv:         $VENV_DIR"
echo "  CUDA toolkit: $CUDA_HOME"
echo "  Model:        $MODEL"
echo "  Served name:  $SERVED_MODEL_NAME"
echo "  Port:         $PORT"
echo "  HF Cache:     $HF_HOME"
echo "  Engine Cache: $XDG_CACHE_HOME/freetoken"
echo "  Attention:    auto (model/runtime selected)"
echo "  Prefix cache: radix + usage reporting"
echo "  CPU MoE sync: automatic fast handshake with driver fallback"
echo "  Memory ratio: $MEMORY_RATIO"
echo "  KV reserve:   $KV_RESERVE_TOKENS tokens"
echo "  Prefill chunk:$MAX_PREFILL_LENGTH tokens"
echo "  Prefill D2D:  $MOE_PREFILL_HIT_D2D"
echo "  Max requests: $MAX_RUNNING_REQUESTS"
echo "  CUDA graph:   $CUDA_GRAPH_MAX_BS"
if [[ -n "${FREETOKEN_GGUF_HOST_CXX:-}" ]]; then
  echo "  GGUF host CXX:$FREETOKEN_GGUF_HOST_CXX"
fi
if [[ -n "$MOE_CACHE_SIZE" ]]; then
  echo "  MoE cache:    $MOE_CACHE_SIZE slots (explicit)"
fi
if [[ -n "${FREETOKEN_BENCHBW_PATH:-}" ]]; then
  echo "  BW profile:   $FREETOKEN_BENCHBW_PATH"
else
  echo "  BW profile:   not found; FreeToken auto-discovery will be used"
fi
if [[ "${LOCAL_MOE_RECOVERY:-0}" == "1" ]]; then
  echo "  Startup mode: ${LOCAL_MOE_CONTEXT_PROFILE:-recovery}"
elif [[ -n "${LOCAL_MOE_GPU_START_MODE:-}" ]]; then
  echo "  Startup mode: ${LOCAL_MOE_GPU_START_MODE}"
else
  echo "  Startup mode: ${LOCAL_MOE_CONTEXT_PROFILE:-balanced12k}"
fi

exec "$VENV_DIR/bin/ft" serve \
  --model-path "$MODEL" \
  --served-model-name "$SERVED_MODEL_NAME" \
  --port "$PORT" \
  --host 127.0.0.1 \
  --memory-ratio "$MEMORY_RATIO" \
  --kv-reserve-tokens "$KV_RESERVE_TOKENS" \
  --max-prefill-length "$MAX_PREFILL_LENGTH" \
  --max-running-requests "$MAX_RUNNING_REQUESTS" \
  --cuda-graph-max-bs "$CUDA_GRAPH_MAX_BS" \
  --cache-type radix \
  --enable-cache-report \
  --sampling-defaults model \
  --disable-moe-prefill-overlap \
  "${PREFILL_ARGS[@]}" \
  "${EXTRA_SERVE_ARGS[@]}" \
  "$@"
