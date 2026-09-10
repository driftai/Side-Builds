#!/usr/bin/env bash

# Configure the project-local CUDA toolkit installed into the FreeToken venv.
# This file is sourced by setup and runtime entry points; it intentionally does
# not change shell options or execute anything on its own.
local_moe_configure_cuda() {
  local python_path="${1:?FreeToken Python path is required}"
  local cuda_root

  if [[ ! -x "$python_path" ]]; then
    echo "[Local CUDA] ERROR: FreeToken Python is missing: $python_path" >&2
    return 1
  fi

  cuda_root="$($python_path -c 'import site; from pathlib import Path; print(Path(site.getsitepackages()[0]) / "nvidia" / "cu13")')"
  if [[ ! -x "$cuda_root/bin/nvcc" || ! -f "$cuda_root/include/cuda_runtime.h" || ! -f "$cuda_root/lib/libcudart.so.13" ]]; then
    echo "[Local CUDA] ERROR: project-local CUDA 13 toolkit is incomplete at $cuda_root" >&2
    echo "[Local CUDA] Run ./scripts/bootstrap.sh to provision it." >&2
    return 1
  fi

  export CUDA_HOME="$cuda_root"
  export PATH="$CUDA_HOME/bin:$PATH"
  export LD_LIBRARY_PATH="$CUDA_HOME/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
}
