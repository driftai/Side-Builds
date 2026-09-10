# Public release qualification

This document defines the final gate before copying Local MoE Harness into the public Side-Builds repository.

## Release-candidate goals

- clean checkout can set itself up without pre-existing runtime/model/environment state;
- Linux/WSL preserves the exact validated FreeToken 8-patch contract;
- native Windows works without WSL using only project-local environments/runtime state;
- native Windows applies only hash-pinned, project-approved FreeToken Python compatibility patches;
- native-Windows GGUF inference does not require an end user to install or activate MSVC/CUDA development tools;
- private-development GitHub sync machinery is not required by end users;
- localhost is the public default;
- project-owned persistent data does not leak into global user locations.

## Linux / WSL clean-room gate

Use a fresh directory with no `runtime/`, `.venv/`, `.venvs/`, `models/`, `.cache/`, `logs/` or `state/`.

Require `./scripts/bootstrap.sh` success, FreeToken HEAD `0ab982f10905fa775962a4eddcb44caa50065251`, APPROVED 8-PATCH BASELINE, project-local persistence, one trusted installed model, and working status/health/models/chat/SSE/cancellation/new-conversation behavior. On the canonical development machine also run a focused Qwen -> Coder -> Qwen regression when those checkpoints are available.

## Native Windows clean-room gate

Use a fresh ordinary Windows directory outside WSL. Require:

1. `Setup.bat` succeeds without FreeToken Desktop.
2. `tools/uv`, `tools/python`, `.venv` and `.venvs/freetoken` are under the tool root.
3. exact wheel hashes in `config/windows-runtime.json` verify before install.
4. every Windows FreeToken compatibility patch declared in `config/windows-runtime.json` verifies by SHA-256, applies strictly to its approved source scope, and fails closed on source-context mismatch.
5. `.venvs/freetoken/Scripts/ft.exe --help` succeeds after compatibility patching.
6. install or externally link a trusted qualification model.
7. `Control.bat` starts the native harness on `127.0.0.1:5180`.
8. FreeToken becomes ready on `127.0.0.1:1919` with exact model identity.
9. chat, SSE, cancellation, fresh conversation and model-selector UI work.
10. Qwen3 Coder is reported `windows_validated`, is selectable when its checkpoint is present, and completes a Coder -> Qwen3.6 return-path regression.
11. external port 1919 occupation is refused rather than silently adopted.
12. Stop terminates only project-owned harness/FreeToken processes.
13. moving the whole project to another folder/drive does not break startup.

### Native-Windows Qwen3 Coder FP8 gate

The official pinned FreeToken Windows wheel requires the approved Qwen3-MoE block-FP8 adapter correction for `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`. Windows setup therefore applies the exact `runtime-patches/freetoken/15-qwen3-coder-fp8.patch` bytes declared by `config/windows-runtime.json` after installing the hash-pinned official wheel.

The Windows qualification requires:

1. patch 15 applies to exactly the five approved `freetoken.models.qwen3_moe` Python files with no rejected context;
2. its block-FP8 imports and adapter hooks import successfully from the resulting project-local Windows venv;
3. conservative profile KV 2048 / prefill 512 / memory ratio .80 / D2D 0 / graph 0 reaches `/health: ok` with exact `/v1/models` identity;
4. normal profile KV 4096 / prefill 1024 / memory ratio .88 / D2D 0 / graph 0 also reaches ready state;
5. short chat, SSE streaming, cancellation, immediate post-cancel generation and `reasoning_effort=none` behavior pass;
6. a subsequent Qwen3.6 launch and generation pass after the Coder runtime is stopped;
7. the disposable canary leaves the production environment untouched until promotion is approved.

The reference native-Windows canary passed both profiles using the official FreeToken `0.1.2+g141c31a8d` wheel. The 2K run retained about 0.58 GiB free VRAM after initialization; the 4K run retained about 0.24 GiB. These geometries remain the approved Coder profiles for this reference hardware rather than implying larger contexts are safe.

## Native-Windows GGUF prebuilt-kernel gate

The official Windows FreeToken GGUF path JIT-compiles a torch CUDA extension on first use. That is not an acceptable public-runtime dependency because it would require an activated compiler/toolkit on each user's machine.

The release candidate therefore requires:

1. `config/windows-gguf-prebuilt.json` to pin the exact Python, FreeToken and Torch compatibility contract.
2. `vendor/windows/freetoken_gguf_kernels.pyd` to be present in the exact locally tested release SHA.
3. `vendor/windows/freetoken_gguf_kernels.json` to record the artifact SHA-256 and build provenance.
4. runtime SHA-256 verification before loading the binary.
5. `scripts/windows-freetoken-entry.py` to inject the prebuilt module into FreeToken's GGUF kernel module before serving a GGUF model.
6. no JIT fallback when the artifact is absent, corrupt, or version-incompatible.
7. an ordinary-shell Gemma canary after the artifact is built, with `cl.exe` and project-local build `nvcc.exe` absent from ordinary runtime PATH.
8. Gemma Q4 GGUF reference geometry: KV 2048, prefill 512, memory ratio .82, D2D 0, CUDA graph 0.
9. `/health`, exact `/v1/models`, chat, SSE, cancellation/scheduler recovery, New Conversation, browser state, owned stop, relocation, and persistence containment to pass using the prebuilt module.
10. the public exporter to retain the qualified `.pyd` and its manifest while still excluding build caches and private qualification evidence.

A release candidate begins in `awaiting_local_build` state. It advances to `validated` only after the binary is built on the required Windows toolchain, the ordinary-shell no-compiler canary passes, and the exact tested artifact plus generated manifest are committed.

## Maintainer-only GGUF build gate

`scripts/build-windows-gguf-kernel.ps1` is release-engineering tooling, not an end-user setup step.

- CUDA compiler/runtime/header components are installed beneath `tools/gguf-builder` from hash-pinned NVIDIA packages.
- The build must use the exact Windows FreeToken/Torch/Python versions recorded in the compatibility config.
- An installed Visual Studio 2022 MSVC toolchain may be explicitly activated for this one maintainer build. This is an explicit build-time exception, not a public-runtime dependency and it is not redistributed by the tool.
- Build caches/output remain beneath the project.
- The produced `.pyd` must be committed only after the no-compiler ordinary-runtime canary passes.
- Qwen3 Coder uses the separately hash-pinned Python compatibility path and does not depend on the GGUF build toolchain.

## Persistence audit

Before and after Windows setup/runtime compare at minimum `%LOCALAPPDATA%\FreeToken`, `%APPDATA%`, `%LOCALAPPDATA%`, `%USERPROFILE%\.cache`, and `%USERPROFILE%\.freetoken`. No new project-owned persistent files may appear there. Child processes are intentionally given project-local AppData/LocalAppData sandboxes.

For Linux/WSL inspect `~/.cache`, `~/.config`, `~/.freetoken`, and similar user-global locations for leaks.

The maintainer GGUF build may inspect/activate an already-installed MSVC Build Tools installation, but it must not install or persist project-owned files there. Its CUDA packages, temporary files, compiler/JIT caches and artifact output remain under the harness root.

## Promotion rule

Do not copy a merely remote-edited tree to Side-Builds. The exact release-candidate SHA must be validated locally on the required hardware. If a real correction or release artifact is needed, the corrected pushed SHA becomes the candidate. Do not create validation-only commits.

Perform the final clean export and Side-Builds promotion only after the exact candidate state has passed its required local qualification gates.