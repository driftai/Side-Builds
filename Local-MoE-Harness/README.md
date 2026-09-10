# Local MoE Harness

A self-contained browser control center for running large local models through FreeToken on either **Linux/WSL2** or **native Windows**.

The harness provides trusted model registration, guarded model switching, GPU-pressure-aware startup profiles, conversation handling, streaming, cancellation, performance telemetry, and a browser UI. Model weights are never downloaded automatically.

## Supported host paths

### Linux / WSL2 — project-validated reference path

The Linux/WSL runtime uses a pinned FreeToken source checkout at `0ab982f10905fa775962a4eddcb44caa50065251` plus the exact approved 8-patch compatibility contract in `runtime-patches/freetoken/manifest.json`.

### Native Windows — project-validated public path

Native Windows runs the harness and FreeToken directly on Windows. It does **not** require WSL.

`Setup.bat` provisions a project-local Python, harness venv, FreeToken Windows venv, downloads, caches, and runtime support files under this folder. It uses official FreeToken Windows engine wheels pinned in `config/windows-runtime.json` and then applies only the hash-pinned Python compatibility patches declared by that manifest; it does not install FreeToken Desktop and does not use `%LOCALAPPDATA%\FreeToken`.

The official FreeToken Windows GGUF path normally JIT-compiles a CUDA extension on first use. Local MoE Harness deliberately removes that end-user compiler requirement: release builds carry a hash-verified `vendor/windows/freetoken_gguf_kernels.pyd` generated from the exact pinned FreeToken/Torch environment. `scripts/windows-freetoken-entry.py` loads that artifact for GGUF models and fails closed if it is missing or incompatible rather than silently using a global MSVC/CUDA toolchain.

Native-Windows support has completed project qualification on the reference RTX 4050 machine. Qwen3.6 passed native-Windows inference after a WSL-to-NTFS migration, Gemma 4 Q4_0 GGUF passed the ordinary-shell compiler-free prebuilt-kernel canary, and Qwen3 Coder FP8 passed native-Windows 2K/4K serving, streaming, cancellation/recovery, and return-to-Qwen qualification. See `docs/PUBLIC_RELEASE.md` for the release gates.

Qwen3 Coder FP8 uses the same approved `15-qwen3-coder-fp8.patch` adapter correction on both supported host paths. On native Windows, setup verifies the exact patch SHA-256 before strictly applying it to the project-local official FreeToken wheel. The patch is confined to `freetoken.models.qwen3_moe`; if the pinned wheel ever stops matching the validated source context, setup fails closed instead of silently enabling an unverified runtime.

## Self-contained storage rule

Persistent runtime/tooling files owned by this tool stay beneath the tool root. Model checkpoint weights are the explicit exception: a user may link a trusted registry model to another local drive, mounted/WSL-visible storage, or removable media.

```text
Local-MoE-Harness/
  .venv/                 harness Python environment
  .venvs/freetoken/      FreeToken environment
  runtime/freetoken/     pinned Linux/WSL source runtime
  models/                default model-weight location + HF cache
  .cache/                package, engine, compiler and JIT caches
  .tmp/                  temporary workspace
  tools/                 setup downloads and managed Python/uv
  vendor/windows/        release-qualified native-Windows binary support
  logs/
  state/                  includes ignored machine-local model-location links
  config/
```

External model locations are configured locally from **Change model → Model storage locations**. Each model can use a different absolute path. The mapping stays in ignored `state/model-locations.json`; personal filesystem paths are not written to the public registry. If a removable drive is absent, its model stays linked but is shown unavailable until the path returns. See `docs/MODEL_STORAGE.md`.

The tool does not intentionally persist project-owned runtime/cache data in AppData, LocalAppData, `~/.cache`, `~/.config`, `~/.freetoken`, or other user-global locations. External prerequisites such as the NVIDIA driver remain system components.

A maintainer may explicitly use an installed MSVC Build Tools environment while producing the Windows GGUF release artifact. That build-time exception is not part of the public runtime: users are not expected to install MSVC or a CUDA toolkit.

See `docs/SELF_CONTAINED_TOOL_POLICY.md`.

## Native Windows quick start

Requirements: Windows 11 x64, an NVIDIA CUDA-capable GPU/driver, PowerShell 5.1+, and Internet access for first setup/model downloads. The public runtime does not require WSL, Visual Studio Build Tools, or a CUDA development toolkit.

```bat
Setup.bat
Control.bat
```

Setup provisions Python and FreeToken inside the project. Install one supported registry model from a terminal, for example:

```bat
.venv\Scripts\python.exe scripts\install-model.py gemma4-26b-q4_0-gguf --dry-run
.venv\Scripts\python.exe scripts\install-model.py gemma4-26b-q4_0-gguf
```

Then use `Control.bat` and open `http://127.0.0.1:5180`.

## Linux / WSL2 quick start

Requirements: x86_64 Linux/WSL2, Python 3 with `venv`, Git, a C++ build toolchain, and an NVIDIA Ampere-or-newer GPU with a CUDA-13-capable driver. A system CUDA toolkit is not required: bootstrap installs pinned CUDA 13 compiler/runtime components inside `.venvs/freetoken` and uses that local toolkit for builds and launches.

```bash
./scripts/bootstrap.sh
./Control.sh
```

`bootstrap.sh` creates local environments, clones pinned FreeToken into `runtime/freetoken`, installs dependencies into `.venvs/freetoken`, applies the approved patch contract, and verifies the runtime. It does not download model weights.

Install a trusted model if the clean checkout does not already contain one:

```bash
.venv/bin/python scripts/install-model.py gpt-oss-20b --dry-run
.venv/bin/python scripts/install-model.py gpt-oss-20b
```

## Model registry and switching

`config/models.json` is the trusted model catalog. Browser/API callers switch by registry ID; model-location overrides only change where the files for that known registry entry are loaded from. They do not allow arbitrary launch commands, runtime flags, served identities, or unsupported model definitions. `config/platform-policy.json` applies host-specific compatibility policy without weakening canonical model records.

Current catalog:

- Qwen3.6 35B A3B NVFP4 — general/default reference model; hardware-qualified on native Windows and validated on Linux/WSL
- Qwen3 Coder 30B A3B FP8 — validated coding specialist and selectable on both Linux/WSL and native Windows
- GPT-OSS 20B — validated Linux/WSL alternate; native-Windows qualification candidate on the 6 GB RTX 4050 reference machine
- Gemma 4 26B A4B Q4_0 GGUF — validated Linux/WSL alternate and hardware-qualified native-Windows GGUF reference model

Cold switching requires authoritative `/health` readiness and exact `/v1/models` identity. Failed switches restore the previous usable model. Switching also clears compact in-process conversation memory.

## Native-Windows GGUF prebuilt artifact

FreeToken's GGUF CUDA kernels are normally compiled through `torch.utils.cpp_extension.load`. The public Windows runtime instead loads an exact prebuilt extension.

Compatibility metadata lives in:

- `config/windows-gguf-prebuilt.json`
- `vendor/windows/freetoken_gguf_kernels.json`

The tracked binary is:

- `vendor/windows/freetoken_gguf_kernels.pyd`

Maintainers reproduce it with `scripts/build-windows-gguf-kernel.ps1`. That script uses hash-pinned project-local NVIDIA CUDA 13 build packages plus an explicitly activated maintainer MSVC environment. After the build, qualification must be repeated from an ordinary PowerShell where `cl.exe`/`nvcc.exe` are not supplied by the host. This proves the public runtime is using the vendored binary rather than silently JIT-compiling.

## FreeToken Linux/WSL integrity contract

Approved runtime = FreeToken `0ab982f10905fa775962a4eddcb44caa50065251` plus exactly:

1. `01-triton-sampling.patch`
2. `02-fi-triton-prefill.patch`
3. `06-triton-activation.patch`
4. `07-activation-pytorch.patch`
5. `08-engine-warmup.patch`
6. `13-fp8-scaled-mm.patch`
7. `14-greedy-sampling.patch`
8. `15-qwen3-coder-fp8.patch`

Verify with `./scripts/verify-freetoken-runtime.sh --verbose`. Do not clean/reset `runtime/freetoken` merely because Git reports tracked modifications; the patched tree is intentional and verifier-owned.

## Network policy

The public default binds the harness to `127.0.0.1:5180` and FreeToken to `127.0.0.1:1919`. LAN exposure is not enabled by default. Absolute model filesystem paths are returned/edited only for loopback clients.

## Public-release status

Linux/WSL clean-room installation and the established model lifecycle are validated. Native Windows setup, self-containment, model installation, process ownership, persistence isolation, relocation, Qwen3.6 inference, Qwen3 Coder FP8 inference/switching, and compiler-free Gemma GGUF inference are validated on the reference machine. Public exports exclude model weights, local environments, runtime state, benchmark artifacts, private qualification material, and private development sync machinery.

## Third-party software

This harness is MIT licensed. FreeToken is an independent Apache-2.0 project maintained by FlashML. See `THIRD_PARTY_NOTICES.md`.