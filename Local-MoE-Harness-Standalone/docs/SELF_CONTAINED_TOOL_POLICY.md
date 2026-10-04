# Self-contained tool policy

Local MoE Harness follows a standalone-tool storage rule:

> Project-owned persistent files stay inside the tool folder unless the project explicitly defines and validates an external location.

## Owned paths

Expected owned locations include `.venv/`, `.venvs/`, `runtime/`, `models/`, `.cache/`, `.freetoken/`, `.tmp/`, `tools/`, `vendor/`, `logs/`, `state/`, and `config/`.

Windows setup redirects AppData/LocalAppData for child setup/runtime processes into `.cache/windows/...`; it never treats the user's real AppData as this project's engine home.

Linux/WSL launchers set their FreeToken, Hugging Face, pip, Torch, Triton, FlashInfer and temporary roots beneath the project.

## User-selected external model-weight exception

Model checkpoint weights are the one end-user storage category intentionally allowed outside the Harness root.

A user may link a trusted registry model to an absolute directory on another local drive, mounted volume, WSL-visible location, or removable/external drive. The machine-local mapping is persisted only in `state/model-locations.json`, which remains inside the Harness root and is ignored by Git.

This exception applies only to the checkpoint files for an existing trusted registry model. It does **not** authorize external locations for:

- Python or FreeToken virtual environments;
- the FreeToken runtime checkout;
- application state, logs, or settings;
- setup/download tooling;
- package, compiler, Torch, Triton, FlashInfer, or application caches;
- vendored release artifacts;
- arbitrary commands or unregistered model definitions.

The model registry still owns model identity, required-file validation, served-model identity, runtime profiles, and platform compatibility. Linking a filesystem path never turns an arbitrary model into a supported registry entry.

A disconnected removable drive is not a failure of the Harness's self-contained runtime. The saved model link remains machine-local and the affected model is treated as unavailable until the path returns.

See `docs/MODEL_STORAGE.md`.

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

A setup or public-runtime path that requires project-owned persistent state outside the project root is a release blocker **unless it is the explicit user-selected model-weight exception above**. Do not work around failures by installing FreeToken Desktop, a global Python environment, a user-global cache, or an undeclared global compiler/toolkit.

## Verification

Public qualification must compare user-global persistence locations before and after setup/runtime use and verify that new project-owned files appear only beneath the tool root, except for model checkpoint files intentionally linked to a user-selected external location.

External-model qualification must verify that:

- the linked path remains machine-local state and does not enter Git-tracked configuration;
- required checkpoint files are validated at the linked location;
- an offline/removable path is reported unavailable rather than silently copied or replaced;
- switching launches the registered served-model identity from the linked path;
- resetting the link restores the registry's default project-local path.

For the Windows GGUF release path, qualification also verifies the tracked `.pyd` SHA-256, exact FreeToken/Torch/Python compatibility, ordinary-shell inference without `cl.exe`/`nvcc.exe`, and relocation of the complete tool folder.