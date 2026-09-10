# Self-contained tool policy

Local MoE Harness follows Drift's standalone-tool storage rule:

> Project-owned persistent files stay inside the tool folder unless the project was explicitly designed to use an external location.

## Owned paths

Expected owned locations include `.venv/`, `.venvs/`, `runtime/`, `models/`, `.cache/`, `.freetoken/`, `.tmp/`, `tools/`, `vendor/`, `logs/`, `state/`, and `config/`.

Windows setup redirects AppData/LocalAppData for child setup/runtime processes into `.cache/windows/...`; it never treats the user's real AppData as this project's engine home.

Linux/WSL launchers set their FreeToken, Hugging Face, pip, Torch, Triton, FlashInfer and temporary roots beneath the project.

## External prerequisites

System-level NVIDIA drivers and OS facilities are prerequisites rather than application state and are not copied into the project.

The public native-Windows runtime does not require a global Python, FreeToken Desktop, MSVC Build Tools, or a CUDA development toolkit.

## Explicit maintainer-build exception

FreeToken's Windows GGUF kernel is a torch CUDA extension that upstream normally JIT-compiles. To keep the end-user runtime self-contained, Local MoE Harness produces a release-qualified prebuilt `.pyd` during release engineering.

That one maintainer build may explicitly activate an already-installed, supported Visual Studio MSVC Build Tools environment. This exception is limited to producing the redistributable project artifact:

- it is never a silent runtime fallback;
- it does not authorize setup to install or mutate Visual Studio globally;
- CUDA 13 build components, caches and temporary outputs remain hash-pinned and project-local under `tools/gguf-builder`/`.cache`;
- the resulting `vendor/windows/freetoken_gguf_kernels.pyd` and hash manifest become part of the project release;
- ordinary runtime qualification must be repeated from a shell without the maintainer compiler/toolkit environment.

If the prebuilt module is absent or incompatible, native-Windows GGUF must fail with evidence rather than invoking a global compiler.

## Failure rule

A setup or public-runtime path that requires project-owned persistent state outside the project root is a release blocker. Do not work around it by installing FreeToken Desktop, a global Python environment, a user-global cache, or an undeclared global compiler/toolkit.

## Verification

Public qualification must compare user-global persistence locations before and after setup/runtime use and verify that new project-owned files appear only beneath the tool root.

For the Windows GGUF release path, qualification also verifies the tracked `.pyd` SHA-256, exact FreeToken/Torch/Python compatibility, ordinary-shell inference without `cl.exe`/`nvcc.exe`, and relocation of the complete tool folder.
