# VoxelVision

Interactive 3D Voxel Video Engine & Audio-Reactive Media Lab.
*Inspired by [VoxelTV](https://voxeltv.surge.sh/) by Joey Cato.*

## Overview

VoxelVision turns ordinary 2D video into an interactive voxel relief inside Three.js/WebGL. The bundled public-safe procedural demo includes a matching authored depth cache, while imported local videos and YouTube URLs use selectable enhanced DA3 or balanced DA2 live depth in the browser.

The renderer remains local-first: Three.js and the bundled demo are local assets, and live AI is loaded only when a non-cached source is used.

This public distribution does not contain privately tested videos, browser cache data, machine-specific configuration, or downloaded helper executables. See [Third-Party Notices](THIRD_PARTY_NOTICES.md) for provenance and runtime model information.

## v1.9.2 - Temporal Stability + Cache Sampling

v1.9.2 strengthens stable-region depth anchoring, applies motion-aware stabilization to cached fusion, and separates cache sampling density from the visible live-depth rate. The cache can retain additional source frames for smoother replay without pretending inference itself became faster.

- Stable visual regions resist unrelated background-driven depth pumping.
- Cache generation avoids the old post-seek callback timeout and can sample at source-aware 24/30/60 FPS targets.
- Foreground recovery searches conservatively across soft model boundaries and tolerates bounded lighting shifts.
- Generated test diagnostics remain inside the project and passing verification stays summary-only.

## v1.9.1 - Foreground Detail + Durable Resume

v1.9.1 repairs compact foreground regions that the monocular model incorrectly merges into the background and makes interrupted analysis profiles resume deterministically after a reload.

- A conservative mask-guided pass uses confirmed model foreground contacts plus color boundaries to recover missed illustrated hair, headwear and similar thin detail. Color never invents near/far geometry by itself, border-connected regions are rejected, and lift is bounded.
- The recovery runs while new maps are conditioned and once per cached depth pair during rendering, so previously stored v1.9.0 maps gain the repair without duplicating or invalidating their cache.
- Re-importing the same local file or YouTube identity now selects the strongest saved model/backend/detail/FPS profile before model initialization. Portrait and landscape profiles use true max-edge detail semantics.
- Each completed frame remains an independent IndexedDB transaction. After a tab reload or lost connection, actual stored frame keys override delayed metadata counters and unfinished analysis continues from its saved maps to completion.
- Manual and Auto targets are restored separately from the cached active grid/FPS, preventing warm-model status events from silently replacing the selected cache profile. Cache cards now show analyzing, paused/resumable, or complete state.

The detail repair follows mask-guided depth-refinement findings for blurry object boundaries and missed thin structures, while the recovery lifecycle follows IndexedDB's transaction durability guidance rather than relying on unload-time writes.

## v1.9.0 - Reusable Source Timeline

v1.9.0 makes cached depth belong to the video timeline instead of behaving like unrelated work for every FPS/detail choice.

- Compatible model results are reused lazily across grid and depth-FPS profiles. Exact timestamps at equal-or-better detail are final; missing intermediate timestamps interpolate immediately and remain eligible for native refinement. Persistent blobs are referenced rather than copied.
- Cached playback is driven by the decoded frame presentation timestamp and continuously interpolates aligned depth endpoints. Chained robust scale/shift alignment suppresses frame-wide height pumping without crossing scene cuts.
- **Cached Playback Depth** shows the exact fused cache frame currently feeding geometry, including media time, map pair, blend, origin and native/shared coverage.
- Auto detail/motion modes reuse the most recent valid inference measurement immediately, then retain their existing hysteretic downshift/recovery behavior.
- The library groups one video's profiles under one card, exposes source title/URL and score sample count in compact reports, and supports confirmed per-video deletion plus double-confirmed **Clear All**.
- Conversion quality is sampled once per newly analyzed depth map. Final partial batches are flushed when a source/profile changes, so counts no longer stop at the last 12-frame persistence checkpoint.

The sync/reuse design follows browser presented-frame timestamps, overlapping/key-frame-aligned video depth, and image-guided depth upsampling principles: [requestVideoFrameCallback](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback), [Video Depth Anything](https://openaccess.thecvf.com/content/CVPR2025/papers/Chen_Video_Depth_Anything_Consistent_Depth_Estimation_for_Super-Long_Videos_CVPR_2025_paper.pdf), and [Joint Bilateral Upsampling](https://johanneskopf.de/publications/jbu/paper/FinalPaper_0185.pdf).

## v1.8.2 - Compact Generation Reports

v1.8.2 keeps copied feedback focused on how the video was converted. Reports contain only depth-generation settings, cache/recalibration state, compact automatic score components and the user's review. Machine specifications, source identities, dates, runtime snapshots, confidence prose and duplicate metadata are omitted.

## v1.8.1 - Portable Conversion Feedback

v1.8.1 turns each cached conversion into a reviewable diagnostic record that can be copied into a development conversation.

- Cache cards expose the automatic score and its edge alignment, temporal stability, relief, border integrity and precision components instead of showing only the combined grade.
- A user review can store a 1-10 quality score, structured artifact flags and free-form scene notes with the exact model/grid/FPS cache variant. Replaying and pausing the variant before saving records the observed playback timestamp.
- **Copy Report** emits a compact JSON diagnostic packet containing cache completion, model/backend/precision, calibration, automatic assessment, generation environment, current runtime state and the user review.
- Reports intentionally omit raw source identities and URLs. Feedback persists in browser-local IndexedDB and survives cache-library refreshes and page reloads.
- The feedback/report smoke is deterministic and summary-only so the additional coverage does not add repetitive verification output.

## v1.8.0 - Model + Video Evidence Fusion

v1.8.0 combines the stable playback principles explored by VoxelTV with VoxelVision's newer live models and decoded-video evidence.

- The original site demonstrated how precomputed keyframes, scene-cut-aware interpolation and cheap GPU extrusion can provide smooth relief playback. The public VoxelVision package uses its own procedural media/depth pair instead of redistributing that site's media.
- Cached and analyzed depth now interpolate on each decoded video frame, then receive a bounded edge-aware refinement from the matching video image. The model remains the only near/far authority, so brightness and texture cannot invent voxel height.
- New analysis stores compact luma guides beside 16-bit depth maps. These guides support temporal scoring and stable boundary placement without increasing model or VRAM requirements.
- The source panel now includes a browser-local cache library. Each quality profile shows model/grid/FPS/completeness and can restore its source and settings for immediate replay.
- Local video blobs and stable imported-video URLs are retained with cache metadata when browser quota permits. Missing sources fail clearly and can be reattached without invalidating compatible depth data.
- Recalibration is non-destructive: original frames remain untouched while a scene-aware median/span overlay reduces frame-wide height pumping without smoothing across cuts.
- Every conversion receives a no-reference 0-100 estimate based on temporal stability, image/depth edge agreement, useful relief, border integrity and precision. It is explicitly a consistency/plausibility signal, not metric-depth ground truth.
- New fusion, scoring and recalibration modules stay below the project's 450-line modularization boundary and verification remains summary-first.

## v1.7.0 — Analyze-Ahead Hybrid Depth Cache

v1.7.0 decouples AI analysis from visible playback so system RAM and local browser storage can absorb inference delays instead of leaving stale voxel frames on screen.

- Hybrid playback is the default for imported videos. A separate hidden decoder analyzes the current position first, then fills roughly eight seconds ahead and continues through the full video in the background.
- Playback reads synchronized depth from a bounded least-recently-used RAM queue. The budget scales conservatively with detected system memory (about 512 MB on a 64 GB machine); model inference and rendering remain constrained by GPU compute/VRAM.
- Every generated map is persisted in browser-managed IndexedDB as normalized 16-bit depth. Repeat playback and seeking reuse the cache while live Float32 geometry keeps full renderer precision.
- Cache identities include source, duration, aspect, grid, FPS, active model/backend/precision, inversion and processing-pipeline version. Incompatible quality or future model changes create a clean variant rather than reusing stale maps.
- The controller prebuffers the current and following depth samples, prioritizes seeks, preserves temporal processing for sequential analysis, and invalidates in-flight work safely when a second local or YouTube source is loaded.
- **Live only** remains available for users who prefer zero intentional startup buffering and no persistent analysis cache.
- Video Depth Anything Small was evaluated but is not enabled: its official FP16 benchmark uses about 6.8 GB VRAM, above the target RTX 4050's 6 GB, while the installed PyTorch runtime is CPU-only. System RAM cannot substitute for that compute/VRAM requirement without making conversion impractically slow.
- Verification now has a quiet summary-first runner. Passing detail is captured instead of printed; failures receive bounded context and a machine-readable artifact in the ignored `test-results/` directory.

## v1.6.1 — DA3 FP16 WebGPU Compatibility

v1.6.1 keeps the enhanced DA3 FP16 model accelerated on Chrome/D3D systems whose WebGPU compiler rejects its cubic resize shader.

- DA3's single `/backbone/Resize` positional-grid operation is routed to the CPU through ONNX Runtime's per-node WebGPU session option. The original cubic math and FP16 model stay intact; the transformer backbone and depth head remain on WebGPU.
- A validated DA3 WebGPU Q8 tier remains available if a browser/runtime does not support per-node routing, before the tool considers WASM or the balanced DA2 model.
- Worker sessions now carry model-specific ONNX session options without leaking those settings into other depth profiles.
- The real Chrome/RTX regression pass requires DA3 FP16 Hybrid at true `512 × 384`, checks the 518-class model input, and fails on any browser console error.

## v1.6.0 — Stable Motion + Explicit Quality Control

v1.6.0 makes adaptation opt-in and treats video-depth continuity as part of geometric quality.

- Manual Lock is now the default: selected detail and FPS are never silently changed by runtime measurements.
- Auto Detail Priority preserves the selected grid while FPS downshifts quickly and recovers upward after sustained headroom.
- Auto Motion Priority preserves the selected FPS by stepping both real model input and voxel detail down first, with a 4+ FPS goal when the runtime can sustain it; detail and FPS recover one tier at a time.
- Both DA3 and DA2 inference run in isolated workers, and full RGBA buffers transfer without an avoidable main-thread copy.
- Relative-depth percentile bounds expand quickly but contract slowly, while a conservative median/span anchor stops near-static scenes from changing their whole height scale between predictions.
- Small camera translations are estimated from the decoded video and applied to temporal depth history, reducing moving-edge ghosts without blending across scene cuts.
- Completed predictions carry their decoded media timestamp. Busy periods collapse to one latest-frame request, stale frames skip extra cross-fade latency, and normal handoffs start from the currently visible interpolated surface.
- Adaptive detail changes resample the visible Float32 surface instead of clearing the panel, and every landscape, portrait, square, and ultrawide tier remains aspect-safe and ViT patch-aligned.
- Warm-model readiness is re-announced per source, fixing a second YouTube import that could remain stuck on the Loading badge.

## v1.5.0 — Enhanced Depth Model Architecture

v1.5.0 upgrades raw geometric placement while keeping the existing stability and Float32 conditioning pipeline.

- Enhanced mode uses the Apache-2.0 Depth Anything V3 Small browser export for stronger monocular geometry, with Depth Anything V2 Small retained as an automatic compatible fallback.
- Model profiles explicitly define tensor rank, patch size, output direction, tone mapping, licensing and fallback order. A future model cannot silently reverse near/far relief.
- Every AI configuration must execute a finite, non-constant, depth-like warm-up field before the UI reports it ready.
- Enhanced-model inference runs in a dedicated worker. WebGPU and WASM attempts get isolated ONNX runtimes, so a driver shader failure cannot poison fallback or block the render/UI thread.
- Inference canvases are ViT patch-aligned without stretching the source. Replicated padding is cropped from model output before voxel placement for landscape, portrait, square, ultrawide and extreme aspect ratios.
- DA2 inverse depth receives a logarithmic transfer before robust temporal normalization, expanding distant geometry that linear scaling compressed into stacked shelves.
- Model changes cancel stale results, dispose the old session, reset temporal state and runtime measurements, and preserve the measured bidirectional FPS governor.
- The selected and actually active model are exposed in status badges and depth diagnostics, including truthful automatic-fallback state.

## v1.4.0 — Adaptive Depth Fidelity + Recovering Performance

v1.4.0 replaces fixed scene assumptions with a reusable, aspect-independent depth-conditioning pipeline.

- Live AI and Luma depth share pure, testable Float32 processing without reintroducing 8-bit height terracing.
- Robust row/column profiles suppress excessive whole-panel bias while retaining local object depth and visually supported perspective.
- Confidence-gated color guidance protects supported boundaries without copying video texture into depth.
- Border repair works on localized, aspect-relative segments and only tapers uniform extreme bands that lack credible visual support.
- Relief compression responds to measured broad-bias strength instead of applying a fixed crop, bottom flatten, or resolution-specific constant.
- A Raw Model / Normalized / Stabilized / Final diagnostic view shows where an artifact enters the pipeline and reports bias, repair and relief metrics.
- The FPS governor is now a standalone tested policy using rolling EMA and p90 timing: overload downshifts quickly, sustained headroom recovers one tier at a time, and the original user request remains remembered.
- Real browser verification covers 16:9 `512 × 288`, portrait `288 × 512`, and ultrawide `512 × 128` grids on WebGPU FP16.

## v1.3.0 — Stability + Guided Voxel Motion

v1.3.0 hardens live conversion during source changes and improves temporal detail without raising the model or voxel budget.

- In-flight depth jobs carry a generation token. Results from an old source, seek position, aspect, inversion, or detail grid are discarded instead of contaminating new buffers.
- Seeking and detail changes reset temporal history, preventing unrelated frames or mismatched grid sizes from blending together.
- One failed AI frame now preserves the last stable voxel surface. Three consecutive failures trip a controlled Luma fallback and dispose the failed pipeline instead of flashing between AI and Luma indefinitely.
- Runtime timing ignores cancelled frames and backend transitions, so one failure cannot create a misleading FPS cap.
- Temporal stabilization now uses the matching video colors as motion guidance. Stable surfaces stay calm while moving edges update faster, reducing voxel trails around subjects.
- Scene-cut detection combines depth change with visual change, catching hard cuts whose model output happens to have a similar depth range.
- Live depth interpolation uses a smoothstep curve for gentler motion between inference frames.
- A dedicated live-depth stability smoke suite protects the new guidance, cut detection, and temporal behavior.

## v1.2.9 — Verified WebGPU Depth + Honest 512 Detail

v1.2.9 fixes the live transformation path and makes the quality controls describe what is really rendered.

- The Transformers.js browser import now uses the supported package-root ESM entry. The previous direct `dist` import left `onnxruntime-web/webgpu` unresolved and silently sent live videos to luminance fallback.
- The 512 tier now produces a true `512 × aspect` grid. For example, 4:3 is `512 × 384`, 16:9 is `512 × 288`, and portrait 9:16 is `288 × 512`.
- Detail tiers describe the longest edge, matching Depth Anything's aspect-preserving 518-class input. Higher tiers would add render cost without adding meaningful model detail.
- Live color extraction and depth scheduling use decoded-video-frame callbacks when available, avoiding repeated work on the same frame and preventing paused videos from generating false benchmark samples.
- Scene cuts now snap to the new depth frame instead of cross-fading unrelated shots.
- Luma's bilateral smoothing reuses precomputed Gaussian weights, preserving the same edge-aware result with substantially less main-thread math.
- Runtime inference timing still retracts unsustainable FPS choices. On the local RTX 4050 verification run at true 16:9 `512 × 288`, WebGPU FP16 measured around `150–190 ms/frame`, moving between 3 and 4 FPS as scene cost changed.

## v1.2.3 — Self-Tuning Detail + Point-Aware Zoom

v1.2.3 removes two usability problems from the first hardware-aware build.

### Hardware Detail Unlocks Itself

The live grid and AI-rate tiers no longer depend on anyone manually inspecting the machine. VoxelVision profiles itself every time it starts.

The local Node server exposes a small `/api/hardware` capability response containing:

- CPU model
- logical CPU thread count
- total system RAM
- locally detected GPU names (Windows uses `Win32_VideoController`; macOS/Linux use platform fallbacks)

The browser combines those local system facts with:

- WebGPU availability and adapter limits
- WebGPU adapter information when available
- WebGL renderer information as another fallback
- real measured Depth Anything inference time during playback

The result is still classified into **Safe / Balanced / Performance / Extreme**, but GPU-name privacy/restrictions inside the browser no longer force an otherwise capable standalone PC into an unnecessarily low profile.

### Grid Tiers Are Hardware-Gated, Not Source-Gated

Supported machines can select their unlocked live-grid tier even while the bundled procedural demo is active:

- **512 max-edge detail** — Extreme
- **384 max-edge detail** — Studio
- **256 max-edge detail** — Cinema
- **192 max-edge detail** — Sharp
- **128 / 96 / 64 / 48 max-edge detail** — lower tiers

The procedural demo renders from its authored `128 × 72` cache. Selecting a higher tier while cached simply stores that value as the **next live-video preset**. When a YouTube/local live source loads, VoxelVision applies the selected live resolution automatically.

Unsupported tiers remain disabled according to the current machine profile.

### Point-Aware Smooth Zoom

The camera now uses OrbitControls' cursor-aware dolly path instead of always tunneling toward one fixed scene-center target.

- Mouse wheel zooms toward the exact screen point under the cursor.
- Hold the **middle mouse button** and drag vertically for continuous point-aware dolly zoom.
- Zoom speed is reduced for finer control between near and far views.
- Dynamic safety limits still prevent entering the voxel surface or disappearing into scene fog.
- The safe near limit updates when Voxel Height Scale changes.

This gives the camera a continuous usable range rather than making wheel input feel like switching between one distant shell and one close shell.

## v1.2.2 — Hardware-Aware Live Quality

v1.2.2 expanded live grid detail and AI depth-rate controls without exposing every heavy setting to every machine.

VoxelVision builds a capability profile from available hardware/browser signals. Each profile gets its own maximum live-grid size, voxel budget and initial AI-depth FPS ceiling.

### Capability-Aware Live AI Depth Rate

The live depth selector contains **1 / 2 / 3 / 4 / 6 / 8 / 10 / 12 FPS** targets.

Hardware profiling decides which targets are initially allowed, but VoxelVision then performs a second, more important check during real playback: it measures actual end-to-end Depth Anything inference time after the model is initialized.

After several samples, VoxelVision estimates a safe sustained AI rate with performance headroom. If the browser/GPU cannot really sustain a high target, unsupported FPS options are disabled and an over-limit selection is automatically reduced to the nearest safe tier.

This means laptop power limits, browser WebGPU behavior, thermals and the active FP16/Q4 model path can influence the live ceiling instead of trusting a GPU model name alone.

The settings drawer shows the active hardware profile and, once enough live frames have been measured, the observed AI milliseconds per frame and current safe FPS ceiling.

## v1.2.1 — High-Fidelity Depth Transformation

v1.2.1 focuses on the quality of the **2D video → depth → voxel sculpture** transformation itself.

### Better AI Input

- Live depth capture targets the model's normal **518-class** input instead of the previous 448-wide intermediate frame.
- Landscape, portrait and square videos preserve their true aspect ratio before depth inference.
- Canvas scaling uses high-quality smoothing when preparing AI input.

### Higher-Precision WebGPU Depth

On WebGPU, VoxelVision tries the Depth Anything V2 Small ONNX model in this order:

1. **FP16** — preferred high-fidelity path
2. **Q4F16** — lower-memory WebGPU fallback
3. **Q4** — compatibility WebGPU fallback
4. **WASM Q4** — CPU/WASM fallback when WebGPU cannot initialize

### Raw Depth Instead of Preview Depth

VoxelVision prefers the model's raw floating-point `predicted_depth` tensor and performs its own stable normalization instead of relying only on the display-oriented per-frame grayscale depth image.

### Depth Reconstruction Quality

The live transform applies:

- robust 2% / 98% percentile depth normalization
- stabilized depth-range bounds across adjacent frames
- **bilinear** depth resampling into the voxel grid
- light spatial edge refinement
- motion-aware temporal stabilization
- scene-cut detection
- GPU A/B interpolation between AI frames

## v1.2.0 — Source Fidelity & High-Detail Live Grids

v1.2.0 separated **source quality** from **voxel-grid quality**.

### Quality-Aware YouTube Import

The YouTube panel exposes:

- **720p** — faster/smaller
- **1080p** — default and recommended
- **1440p** — high quality
- **2160p / 4K** — very high quality
- **Source Max** — best source yt-dlp can obtain

When FFmpeg is available, VoxelVision tries adaptive video-only + audio-only streams first. FFmpeg merges/remuxes those streams locally without intentionally re-encoding the video.

The resulting file is stored under `public/media/imported/` and served through the native HTTP range server.

### Actual Source Quality Reporting

When `ffprobe` is available, VoxelVision reports the downloaded video's actual:

- width × height
- approximate quality tier
- frame rate
- video codec

## YouTube Ingestion Flow

1. Paste a public `youtube.com` or `youtu.be` video URL.
2. Choose the desired source-quality tier.
3. `yt-dlp` selects the best video at or below that tier (or Source Max).
4. If FFmpeg is available, adaptive video/audio streams are preferred and merged locally.
5. The local media file is served through VoxelVision's HTTP range server.
6. Browser frames provide per-voxel RGB color.
7. An aspect-correct 518-class frame is prepared for live AI depth.
8. Depth Anything V2 Small estimates raw relative depth through Transformers.js.
9. VoxelVision stabilizes, refines and resamples that raw depth into the active voxel grid.
10. WebGPU is preferred; WASM is the fallback.
11. Live AI depth frames are smoothly interpolated by the GPU depth A/B shader path.

## Local Video Import

Drag/drop or choose any browser-supported video. Local files use their own live depth pipeline instead of inheriting the procedural demo geometry. Their decoded dimensions are shown in the source-quality badge.

## Live Depth Controls

- 1 / 2 / 3 / 4 / 6 / 8 / 10 / 12 FPS targets, filtered by hardware and measured runtime performance
- WebGPU FP16 first, with quantized and WASM fallbacks
- raw-depth temporal range stabilization
- bilinear grid resampling and edge refinement
- smooth interpolation between live AI depth frames
- optional depth inversion
- up to 512 / 384 / 256 / 192 / 128 / 96 / 64 / 48 live max-edge detail depending on machine profile
- profile-specific total-voxel safety budgets
- cached depth remains capped to its authored maximum instead of being artificially upscaled

## Setup

### Launch

Double-click `VoxelVision.bat`, or:

```bat
cd path\to\Side-Builds\VoxelVision
npm start
```

Then open `http://127.0.0.1:9095`.

### Recommended YouTube Setup

From `VoxelVision.bat`, choose:

```text
[4] Setup / Update YouTube Support (yt-dlp + FFmpeg)
```

The launcher installs/updates the standalone yt-dlp plus portable FFmpeg/FFprobe runtime used by the YouTube bridge.

### Verify Code

```bat
npm run verify
```

This runs syntax checks plus smoke tests for YouTube quality selection, hardware capability profiling, aspect-independent depth fidelity, temporal anchoring, latest-frame state, bidirectional FPS recovery, and all three quality-tuning modes.

## Live AI Model

VoxelVision lazily loads the selected browser model:

```text
en970/depth-anything-v3-small-onnx (Enhanced)
onnx-community/depth-anything-v2-small-ONNX (Balanced)
```

through Transformers.js when live depth is first requested. Both execute in isolated workers. DA3 uses FP16 Hybrid (one cubic resize on CPU, all inference-heavy work on WebGPU) and falls back through validated WebGPU Q8/WASM configurations when necessary.

## Architecture

```text
VoxelVision/
├── VoxelVision.bat
├── server.js
├── youtube-import.js
├── package.json
├── README.md
├── scripts/
│   ├── youtube-quality-smoke.mjs
│   ├── capability-profile-smoke.mjs
│   ├── live-depth-stability-smoke.mjs
│   └── adaptive-fps-governor-smoke.mjs
├── tools/
│   ├── .gitignore
│   ├── yt-dlp.exe
│   ├── ffmpeg.exe
│   └── ffprobe.exe
└── public/
    ├── index.html
    ├── css/style.css
    ├── vendor/
    │   ├── three.module.js
    │   └── OrbitControls.js
    ├── js/
    │   ├── app.js
    │   ├── audio-reactive.js
    │   ├── capability-profile.js
    │   ├── depth-engine.js
    │   ├── depth-processing.js
    │   ├── adaptive-fps-governor.js
    │   ├── hardware-autotune.js
    │   ├── live-depth.js
    │   ├── point-zoom.js
    │   └── voxel-scene.js
    └── media/
        ├── voxelvision-demo.mp4
        ├── voxelvision-demo.depth.json
        ├── voxelvision-demo.depth.bin.gz
        └── imported/
```

The demo assets can be reproduced with `npm run generate:demo` after FFmpeg is installed or placed in `tools/`.

## Features

- GPU-instanced voxel rendering and depth interpolation
- cached AI depth plus arbitrary-video high-fidelity live AI depth
- self-detected machine-aware live quality tiers with measured inference auto-tuning
- quality-aware YouTube URL and local-file ingestion
- cursor-point wheel zoom and middle-drag dolly
- 3D Graph and procedural Retro TV modes
- video, charcoal, cyberpunk and phosphor palettes
- audio-reactive voxel extrusion and rim lighting
- camera presets and auto-orbit
- PNG snapshots
- WebM canvas recording with audio capture when supported
- native Node HTTP range serving for smooth video seeking

## Roadmap

- Persist live-generated depth caches so a transformed video becomes fully offline after first analysis
- Background/offline depth precomputation using a heavier depth model for maximum temporal consistency
- Persistent local media/depth library
- Webcam/WebRTC source ingestion
- HLS/custom URL source support where CORS permits frame access
- Bloom/DOF/CRT post-processing passes
- glTF/OBJ voxel export
