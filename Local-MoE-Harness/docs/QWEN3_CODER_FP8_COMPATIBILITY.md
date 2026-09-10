# Qwen3 Coder FP8 compatibility pass

## Status

The compatibility pass is **hardware validated and approved** for the pinned FreeToken runtime.

- Validation harness base: `af52706784d3d5f585d6c412a826f3ef42ba4061`
- Pinned FreeToken: `0ab982f10905fa775962a4eddcb44caa50065251`
- Checkpoint: `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`
- Checkpoint revision: `dcaee4d4dfc5ee71ad501f01f530e5652438fde0`
- Approved patch: `runtime-patches/freetoken/15-qwen3-coder-fp8.patch`
- Approved patch SHA256: `5d7d34e1fdf2c041e3eab9fbf8a9c086d51005374ad83b87f8c5387d35e2ece1`

Nova validated the exact patch bytes on the target RTX 4050 without modifying the live runtime. The candidate copy was then promoted unchanged into the approved runtime contract. The model is now a validated, selectable second Qwen slot; `qwen36-nvfp4` remains the default and ultimate recovery model.

## Validation evidence

Before hardware qualification:

- the exact trusted 12-file model install contained 31,195,082,196 bytes;
- all four safetensor shards matched the approved index;
- the original protected 2K canary loaded the shards but failed before `/health` because the pinned Qwen3-MoE adapter built BF16 attention while the checkpoint supplied block-FP8 `weight_scale_inv` tensors.

The failing unexpected state keys were exactly:

- 48 `model.layers.*.self_attn.qkv_proj.weight_scale_inv`
- 48 `model.layers.*.self_attn.o_proj.weight_scale_inv`

The checkpoint contains 18,624 `weight_scale_inv` tensors total: 192 attention scales and 18,432 routed-expert scales. Its quantization configuration reports FP8 E4M3, dynamic activation quantization, and a `[128, 128]` weight block.

After applying the exact compatibility patch only to a disposable FreeToken checkout, Nova reported:

| Profile | Result | Startup | Expert cache | Generation |
|---|---|---:|---:|---|
| 2K KV / 512 prefill / D2D 0 / ratio .80 / graph 0 | PASS | ~32 s | 346 slots | 3.84 s TTFT, 4.31 tok/s |
| 4K KV / 1024 prefill / D2D 0 / ratio .88 / graph 0 | PASS | ~34 s | 393 slots | 5.38 s TTFT, 5.96 tok/s |
| 3,029-token prompt on the 4K profile | PASS | — | 4,118 KV pages | 14.64 s TTFT, 6.29 tok/s |

Both hardware profiles resolved:

- attention backend: `fi`;
- MoE backend: `offload`;
- expert format: `fp8_block`;
- authoritative `/health` readiness;
- exact `/v1/models` served identity;
- no missing or unexpected tensor keys;
- no CUDA/device failure.

The 2K worker used about 29.57 GiB PSS / 29.75 GiB RSS and about 5.45/6.14 GiB VRAM after initialization. The 4K profile is intentionally the normal ceiling on this machine: FreeToken reported only about 0.06 GiB allocator headroom, but the profile still survived generation, a 419-token sustained decode, and the 3,029-token prompt. Busy and recovery therefore remain on the validated 2K geometry rather than inheriting the 4K profile.

## Functional qualification

The coding-specialist pass covered:

- minimal debugging and patch generation;
- multi-file file-selection reasoning;
- structured Qwen3 Coder tool calling;
- streaming fenced code;
- cancellation and scheduler recovery;
- fresh-conversation isolation;
- iterative correction after an explicit failure;
- near-4K prompt handling;
- ordinary non-thinking output with `reasoning_effort: "none"`.

The model was useful but not perfect at instruction following. During qualification it briefly dropped a lowercase requirement before correcting it after failure feedback, two long-generation prompts ignored strict brevity limits and reached their output caps, and an initial `parse_port` attempt accepted non-ASCII digit strings before a retry fixed the condition. This is a quality caveat, not a runtime-compatibility failure: coding outputs should continue to be verified with tests and explicit constraints.

### Reasoning invariant

This checkpoint is non-thinking. Without `reasoning_effort: "none"`, pinned FreeToken's automatic Qwen3 parser can place the answer in `reasoning_content`. The registry therefore keeps `default_reasoning_effort` set to `none`; that default is part of the validated integration contract and must not be removed casually.

## Root cause

Pinned `qwen3_moe` understands the Qwen3-MoE architecture but its adapter predates native block-FP8 wiring:

1. `qwen3_moe/config.py` did not translate the checkpoint's FP8 config into `ModelConfig.expert_quant` / `weight_block_size`.
2. `qwen3_moe/attention.py` therefore constructed ordinary BF16 `LinearQKVMerged` / `LinearOProj` modules, which have no `weight_scale_inv` parameters.
3. `qwen3_moe/weight.py` already preserved and correctly fused the checkpoint's Q/K/V block-scale tensors, so strict state loading exposed the mismatch immediately.
4. Generic FreeToken already contained block-FP8 dense kernels, the `fp8_block` MoE bank schema, and FP8 expert compute paths.
5. `qwen3_5_moe` already demonstrated the same native 128x128 block-FP8 concepts, but its raw expert-key layout differs, so the correction stays inside the Qwen3-MoE adapter rather than redirecting the checkpoint through Qwen3.5 code.

## Approved correction

The approved patch deliberately changes only the pinned Qwen3-MoE adapter:

- `config.py`
  - recognizes only `quant_method=fp8` with `weight_block_size=[128,128]`;
  - maps it to `expert_quant="fp8_block"`;
  - rejects unknown block geometries instead of guessing.

- `attention.py`
  - preserves the existing BF16 Qwen3 path;
  - uses FreeToken's existing quant-aware block-FP8 dense-linear factories only for block-FP8;
  - limits the new path to TP=1.

- `moe.py`
  - gives resident block-FP8 experts the existing `fp8_block` weight format;
  - leaves BF16 behavior unchanged.

- `weight.py`
  - reuses the existing Qwen3 expert iterator and gate/up + Q/K/V fusion rules;
  - maps the stacked expert tensors into FreeToken's existing four-bank block-FP8 schema: `gate_up`, `gate_up_scale`, `down`, `down_scale`;
  - provides the model-specific `setup_offload_expert_banks` hook required because the generic provider registry intentionally has no catch-all `fp8_block` loader;
  - defers non-FP8 Qwen3 formats to their existing providers.

- `__init__.py`
  - exports the setup hook so FreeToken's model registry can discover it.

No kernel, engine, sampler, cache, or global model-loader code is changed by patch 15.

## Promotion contract

The approved runtime now contains eight patches. Patch 15 must retain the exact validated SHA256 above. `tests/test_qwen3_coder_fp8_patch.py` guards the promoted state: it points at the approved patch, verifies the exact hash, reconstructs pinned FreeToken in `/tmp`, checks the exact five-file source reach, runs `git diff --check`, parses every modified Python source file, and checks the expected FP8 adapter hooks.

After pulling a promotion commit, a local machine that still has the seven-patch working tree must run the normal contract apply/bootstrap path before the active runtime verifier can pass. The final local promotion gate is: apply the approved eight-patch contract, verify it, switch Qwen3.6 -> Qwen3 Coder through the public harness path, confirm the registry-enforced non-thinking default and basic generation, then switch back to Qwen3.6 and verify the eight-patch runtime remains exact.
