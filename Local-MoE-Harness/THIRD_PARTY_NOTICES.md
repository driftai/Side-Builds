# Third-party notices

## FreeToken

Local MoE Harness uses FreeToken as its inference runtime.

- Project: FlashML-org/FreeToken
- License: Apache License 2.0
- Linux/WSL source pin: `0ab982f10905fa775962a4eddcb44caa50065251`
- Linux/WSL applies project-maintained compatibility patches listed in `runtime-patches/freetoken/manifest.json`.
- Native Windows uses official FreeToken Windows engine wheels pinned by URL and SHA-256 in `config/windows-runtime.json`.
- The native-Windows GGUF release artifact is compiled from the GGUF CUDA extension source distributed in the pinned official FreeToken Windows package. Its exact binary hash and compatibility metadata are recorded in `vendor/windows/freetoken_gguf_kernels.json` after release qualification.

FreeToken is maintained independently by FlashML; this harness is not an official FlashML product.

## uv

Native-Windows setup bootstraps the official uv x64 Windows archive into `tools/uv` and verifies the pinned SHA-256 before use. uv is maintained by Astral.

## Ninja

The maintainer-only Windows GGUF artifact build installs a hash-pinned Windows x86-64 `ninja` wheel into the project-owned `tools/gguf-builder` tree. Ninja and the ninja-python-distributions package are Apache License 2.0 software. Ninja is a release-build dependency only; public end users do not need it to run the prebuilt GGUF artifact.

## NVIDIA CUDA Toolkit components

Linux/WSL setup installs pinned NVIDIA CUDA 13 compiler, headers, and runtime packages inside the project-owned FreeToken virtual environment. These components are distributed by NVIDIA and remain subject to NVIDIA's applicable license terms; they are not part of this project's MIT-licensed source.

The maintainer-only Windows GGUF artifact build uses hash-pinned NVIDIA CUDA 13 compiler/runtime/header/compiler-IR packages, including NVVM, under `tools/gguf-builder`. These build packages are not required by ordinary public runtime and are not committed as part of the source release.

## Microsoft Visual C++ Build Tools

The Windows GGUF release artifact may be built by a maintainer using an already-installed supported Microsoft Visual C++ Build Tools environment. Local MoE Harness does not redistribute MSVC and public end users do not need MSVC to run the prebuilt artifact.

## Model licenses

Model weights are not distributed by this repository. Users download selected models from their original repositories and remain responsible for model-specific licenses and terms.
