# Multi-model runtime policy

## Lifecycle contract

FreeToken serves one model per `ft serve` process. The harness therefore treats model replacement as a cold lifecycle operation:

1. exclude new generation and refuse a switch while a request is active;
2. stop only the harness-owned FreeToken process group;
3. resolve the selected registry ID to a trusted local path and model-specific profile;
4. start FreeToken and wait for authoritative `GET /health` readiness;
5. require `/v1/models` to return the configured served-model identity;
6. persist the new local selection and clear incompatible conversation memory;
7. restore the previous installed model, then default Qwen, if any target check fails.

No endpoint accepts arbitrary paths, repositories, command-line flags, or environment variables. Directory checkpoints continue to pass their trusted `local_path`; a single-file model may additionally declare a relative `serve_file` that must be listed in `required_files` and resolve beneath that model's directory. `state/selected-model.json`, model files, Hugging Face cache data, logs, and benchmark artifacts remain local and ignored by Git.

## Machine/profile separation

The startup preflight classifies the GPU as normal, busy, or recovery. `config/models.json` then resolves that machine state to values validated or conservatively proposed for that model. Qwen retains the existing exact contract:

| Machine state | Qwen profile | KV | Prefill | D2D | Memory ratio | Graph | Normal MoE target |
|---|---|---:|---:|---:|---:|---:|---:|
| normal | Balanced 12K | 12,288 | 2,048 | 1 | .92 | 1 | 569 |
| busy | Fast 8K | 8,192 | 2,048 | 1 | .92 | 1 | 736 |
| recovery | Recovery 4K | 4,096 | 1,024 | 0 | .90 | 0 | 736 |

The MoE target informs coexistence restoration; startup still lets FreeToken calculate its cache geometry rather than blindly forcing another architecture's slot count. New architectures begin with conservative 4K/2K, eager-mode profiles and remain experimental until hardware measurements validate them. An eager-to-graph restart occurs only when that model's normal profile actually uses CUDA graphs; GPT-OSS remains eager in every profile and is not restarted merely to change modes.

GPT-OSS 20B was hardware-validated on 2026-09-08 with the normal and busy 4K profiles. Its cold Qwen-to-GPT switch completed in 35.6 seconds, `/health` and `/v1/models` both returned `openai/gpt-oss-20b`, and FreeToken resolved MXFP4 experts to the hybrid backend with Triton attention. A 3,690-token cold prompt completed at 9.39 seconds TTFT, and browser validation passed streaming, separate reasoning, fenced code, copy controls, cancellation, and conversation reset. The busy startup gate measured 4.86 seconds primer TTFT and 2.06 seconds probe TTFT at 12.74 decode tok/s. Qwen remained the default and passed its regression gate after switching back.

## Qwen slot policy

The local harness intentionally targets exactly two Qwen models, not an open-ended set of near-duplicate Qwen checkpoints:

1. `qwen36-nvfp4` is the validated general-purpose/default Qwen and ultimate recovery model.
2. `qwen3-coder-30b-fp8` is the validated second Qwen slot and coding specialist.

A third Qwen should not be added to the live catalog unless it is replacing one of those two roles.

The coding checkpoint is the official `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`, pinned to immutable revision `dcaee4d4dfc5ee71ad501f01f530e5652438fde0`. Qwen documents it as a `Qwen3MoeForCausalLM` model with 30.5B total parameters, 3.3B active parameters, 128 experts with top-8 routing, native 262,144-token context, and non-thinking output. The official repository is about 31.2 GB and uses block FP8 with a 128x128 weight block. The harness downloads only the model/tokenizer/config files required for serving; the repository's Python helper parser is deliberately not part of the trusted download manifest.

Pinned FreeToken `0ab982f...` supported the Qwen3-MoE architecture but its older `qwen3_moe` adapter did not wire this checkpoint's native 128x128 block-FP8 attention and expert banks. The exact source correction was validated on the target RTX 4050 and is now approved as `15-qwen3-coder-fp8.patch` with SHA256 `5d7d34e1fdf2c041e3eab9fbf8a9c086d51005374ad83b87f8c5387d35e2ece1`.

## Model matrix

| Model | Architecture | Payload | Validated backend | Harness state | Rationale |
|---|---|---:|---|---|---|
| `nvidia/Qwen3.6-35B-A3B-NVFP4` | MoE, NVFP4 | 20.9 GB FTW | hybrid | Primary | General-purpose Qwen, current known-good fallback and default. |
| `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8` | Qwen3 MoE, block FP8 | 31,195,082,196 bytes selected root files | `fi` attention + offload `fp8_block` experts | Validated selectable coding specialist | Second and final Qwen slot. Passed exact block-FP8 hardware canaries, near-4K context, streaming, tool calls, cancellation, debugging, multi-file reasoning, and iterative correction. |
| `openai/gpt-oss-20b` | MoE, MXFP4 | 13.79 GB selected root files | hybrid | Validated alternate | Passed identity, generation, streaming, 3,690-token context, UI, persistence, cancellation, and return-to-Qwen gates. Harmony remains FreeToken-owned. |
| `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` | MoE, QAT Q4_0 GGUF | 14,439,363,584 bytes | offload | Validated alternate | Official Google text checkpoint passed 2K canary, normal 4K, streaming, context, cold switching, identity, and return-to-Qwen gates. |

The active registry intentionally contains only validated models and candidates that are still actionable. Conclusively rejected hardware experiments are documented below rather than retained as permanent UI cards.

### Qwen3 Coder validation

The validated profiles on this RTX 4050 are:

| Machine state | Profile | KV | Prefill | D2D | Memory ratio | Graph |
|---|---|---:|---:|---:|---:|---:|
| normal | Coder 4K | 4,096 | 1,024 | 0 | .88 | 0 |
| busy | Coder Busy 2K | 2,048 | 512 | 0 | .80 | 0 |
| recovery | Coder Recovery 2K | 2,048 | 512 | 0 | .80 | 0 |

The exact candidate patch passed 1/1 dedicated compatibility test and the 66/66 Python suite while the live runtime remained on the approved seven-patch baseline. Applied only to a disposable FreeToken checkout, the 2K profile became healthy in about 32 seconds with 346 expert-cache slots, 3.84 s TTFT, and 4.31 tok/s. The 4K profile became healthy in about 34 seconds with 393 slots, 5.38 s TTFT, and 5.96 tok/s. A 3,029-token prompt on 4K completed at 14.64 s TTFT and 6.29 tok/s with 4,118 KV pages. Both profiles selected `fi` attention, offload MoE, and `fp8_block` experts with exact `/health` and `/v1/models` identity and no missing/unexpected state keys or CUDA failures.

The 2K worker used about 29.57 GiB PSS / 29.75 GiB RSS and roughly 5.45/6.14 GiB VRAM after initialization. The 4K profile had only about 0.06 GiB allocator headroom, but survived generation, a 419-token sustained decode, and the 3,029-token prompt; this is why busy/recovery intentionally stay at 2K.

Coding qualification passed minimal debugging, multi-file reasoning, structured Qwen3 Coder tool calls, streaming fenced code, cancellation/recovery, fresh-conversation isolation, iterative correction, and near-4K context. Instruction following was useful but mixed: one follow-up temporarily dropped a lowercase constraint before correction, two long prompts ignored strict brevity limits and exhausted output caps, and an initial `parse_port` attempt accepted non-ASCII digits before a retry fixed it. Treat the model as a validated runtime/coding specialist, not as a guarantee that every strict natural-language constraint will be obeyed without tests.

The checkpoint is non-thinking. `default_reasoning_effort` must remain `none`: without `reasoning_effort: "none"`, pinned FreeToken's automatic Qwen3 parser can place ordinary answer text in `reasoning_content`.

### Gemma Q4_0 validation

The official Google QAT checkpoint is pinned at Hugging Face revision `d1c082be9cf3c8a514acf63b8761f4b41935842e`. The required GGUF is exactly 14,439,363,584 bytes with SHA256 `3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d`. Range-read metadata confirmed `gemma4`, 128 routed experts with top-8 selection, Q4_0 expert tensors, and the Q6_K embedding expected by pinned FreeToken. The optional multimodal projector was not downloaded; harness service remains text-only.

The initial 2K/512-token eager canary selected FreeToken's native offload MoE path, Triton attention, 409 expert-cache slots, and 2,078 KV pages. It became healthy with about .662 GiB free VRAM; the primary engine PSS was 29,386,536 kB. After one-time kernel compilation, a warm streamed prompt measured 2.63 seconds TTFT and about 17.4 tok/s. The final normal 4K/1,024-token profile passed its startup gate at 3.35 seconds primer TTFT and 1.60 seconds probe TTFT. An exact 3,038-token cold prompt completed correctly at 15.63 seconds TTFT without truncating the current user message. Both `/health` and `/v1/models` reported the configured Google model, the public switcher returned to Qwen successfully, and the then-seven-patch runtime stayed unchanged.

Pinned FreeToken's GGUF JIT selected system GCC 13 even though CUDA 12.8 accepts GCC only through 12. The launcher now sets FreeToken's existing `FREETOKEN_GGUF_HOST_CXX` override to installed `g++-12` only for GGUF paths when the user has not supplied an override. Directory-based Qwen and GPT-OSS launches retain their previous environment.

### Historical rejected candidates

- `nvidia/Gemma-4-26B-A4B-NVFP4`: installed and tried twice, but shard 2 failed with `CUDA driver error: device not ready` before readiness. The 18,825,669,933-byte local copy was removed after the Google GGUF replacement passed.
- `nvidia/Qwen3-30B-A3B-NVFP4`: rejected checkpoint, not rejected Qwen family. It was not downloaded because pinned FreeToken's Qwen3 loader does not parse its ModelOpt NVFP4 expert scales. The second Qwen slot instead uses the validated official Qwen3-Coder FP8 checkpoint.
- `RedHatAI/Muse-Glimmer-30B-NVFP4`: not downloaded; dense/fused execution is not viable on the 6.1 GiB GPU.
- `Qwen/Qwen3.5-35B-A3B` BF16: not downloaded; the 71.9 GB checkpoint exceeds the 52 GB WSL memory ceiling and safe machine budget.
- Very large GLM, MiniMax, gpt-oss-120b, and Qwen3.8-Flash-Next's documented 47.7 GiB additional PLE footprint remain excluded without download.

A model belongs in `config/models.json` only when it is validated, is an actively supported experiment, or is an intentionally downloadable candidate awaiting hardware validation. Conclusively incompatible or non-viable entries are removed from the live catalog; their evidence remains here and in Git history.

## Approved runtime-patch reach

The FreeToken contract now contains eight approved patches:

| Patch | Reach |
|---|---|
| `01-triton-sampling` | Global sampling path; all current models can reach it. |
| `02-fi-triton-prefill` | FlashInfer/Triton attention prefill; models resolving to `fi`, including the validated Coder path, use it. |
| `06-triton-activation` | Global activation dispatch; all current models can use it. |
| `07-activation-pytorch` | SiLU/GELU implementations; Gemma/Coder are potentially affected; GPT-OSS's separate SwiGLU-OAI function is not changed. |
| `08-engine-warmup` | Global engine load/warmup behavior; all models use it. |
| `13-fp8-scaled-mm` | Per-tensor FP8 linear compatibility. The Coder's newly validated native block-FP8 linears use the separate block-FP8 kernels rather than this per-tensor path. |
| `14-greedy-sampling` | Global greedy-policy condition; all models potentially use it. |
| `15-qwen3-coder-fp8` | Qwen3-MoE adapter only: detects native 128x128 block FP8, constructs block-FP8 attention, and wires block-FP8 expert banks. Validated on the RTX 4050 with the pinned Qwen3 Coder checkpoint. |

Patch 15 intentionally changes only `python/freetoken/models/qwen3_moe/{__init__,attention,config,moe,weight}.py`. It does not modify kernels, the engine, sampler, cache, or global loader. Its approved SHA256 is `5d7d34e1fdf2c041e3eab9fbf8a9c086d51005374ad83b87f8c5387d35e2ece1`.

## WSL memory result

The host configuration keeps `memory=52GB` as a maximum, not a reservation. In the 2026-09-07 audit, loaded Qwen produced a 21.43 GiB `vmmemWSL` working set; the main FreeToken worker accounted for about 18.99 GB PSS, mostly model-backed shared memory. After a normal harness stop, `vmmemWSL` fell to 4.37 GiB immediately, 2.22 GiB after one minute, and 2.16 GiB after five minutes. Windows available memory rose by about 20.2 GB. The installed WSL default `autoMemoryReclaim=dropCache` is functioning, so `.wslconfig` was not changed and the 52 GB ceiling should remain.

Observed lag correlated instead with roughly 5.7/6.1 GiB VRAM occupied while graphics applications shared the RTX 4050. Reducing WSL's RAM ceiling would not repair that GPU contention and would make MoE host-memory execution less reliable.

## WSL storage accounting

`W:` and `E:\WSL\Ubuntu\ext4.vhdx` are two views of the same bytes. `W:` reports used and available blocks inside the ext4 filesystem; the VHDX file on E: stores those blocks physically. Before the fixed-disk migration, the distro had 350.00 GiB ext4 geometry inside a dynamically expanding VHDX with a 1 TiB virtual maximum. That old 350 GiB filesystem size was not a preallocated Windows allocation.

The apparent Gemma install amplification was a unit-reporting mismatch, not a duplicate checkpoint. The pre-install installer value of about `173.39 GB` used decimal bytes, while the later UI value of about `143.95` divided by `1024^3` but still displayed `GB`. On one basis, current WSL available space plus every file created during the install reconstructs about `173.42 GB` decimal, matching the earlier reading. The only large files created in that interval were Gemma's two approved shards; its model-local Hugging Face metadata occupies about 61 KiB, and no deleted-but-open file was found.

The installer now prints both decimal GB and binary GiB, obtains exact host byte counts, and reports the post-install WSL logical-used, VHDX-file, and Windows-free deltas. It warns without deleting anything if guest consumption exceeds the expected new payload by more than ten percent or 1 GiB, whichever is greater. Browser storage telemetry is explicitly labeled GiB.

The later storage migration replaced that dynamic disk with a fixed, non-sparse 300 GiB VHDX at the same canonical `E:\WSL\Ubuntu\ext4.vhdx` path. Its host file length is 322,128,838,656 bytes and remains constant while guest files are added or deleted. The official Gemma GGUF download consumed 14,456,795,136 logical guest bytes while changing both E: free space and VHDX file length by zero bytes. Deleting the rejected NVIDIA Gemma copy recovered 18,825,669,933 bytes inside Ubuntu while leaving the fixed E: allocation intact. This is the intended accounting: Ubuntu free space changes within an already allocated host file.

## Primary references

- [FreeToken supported models and backend selection](https://github.com/FlashML-org/FreeToken/blob/main/docs/models.md)
- [FreeToken serving quickstart](https://github.com/FlashML-org/FreeToken/blob/main/docs/quickstart.md)
- [Official Qwen3-Coder 30B A3B FP8 checkpoint](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8)
- [Qwen3-Coder project](https://github.com/QwenLM/Qwen3-Coder)
- [OpenAI gpt-oss model architecture](https://openai.com/index/introducing-gpt-oss/)
- [Pinned GPT-OSS 20B repository files](https://huggingface.co/openai/gpt-oss-20b/tree/main)
- [Official Google Gemma 4 QAT Q4_0 GGUF](https://huggingface.co/google/gemma-4-26B-A4B-it-qat-q4_0-gguf)
- [Gemma 4 26B A4B NVFP4 repository files](https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4/tree/main)
- [FreeToken Gemma GGUF quantization compatibility report](https://github.com/FlashML-org/FreeToken/issues/188)
- [FreeToken Gemma GGUF top-k prefill report](https://github.com/FlashML-org/FreeToken/issues/186)
- [Microsoft WSL advanced settings](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
- [Microsoft WSL disk-space architecture](https://learn.microsoft.com/en-us/windows/wsl/disk-space)
- [Microsoft WSL export and import commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
- [Microsoft Hyper-V `Convert-VHD`](https://learn.microsoft.com/en-us/powershell/module/hyper-v/convert-vhd)
- [Hugging Face local-directory download behavior](https://huggingface.co/docs/huggingface_hub/package_reference/file_download)
