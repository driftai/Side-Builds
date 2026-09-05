# Third-Party Notices

VoxelVision's public distribution contains only project-owned demo media. It
does not redistribute the music videos or depth archives used while privately
testing the video-conversion pipeline.

## VoxelTV

VoxelVision was inspired by Joey Cato's public
[VoxelTV](https://voxeltv.surge.sh/) experience. No VoxelTV video, depth cache,
branding, or other media asset is included in this distribution.

## Three.js

The files in `public/vendor/` are from Three.js r160 and are distributed under
the MIT License.

Copyright 2010-2023 Three.js Authors

## Browser depth models

Model weights are downloaded directly by the user's browser and are not stored
in this repository:

- `en970/depth-anything-v3-small-onnx` — Apache-2.0
- `onnx-community/depth-anything-v2-small-ONNX` — Apache-2.0

The browser runtime loads the version-pinned `@huggingface/transformers` 4.2.0
module from jsDelivr. See the upstream package and model cards for their full
license terms and notices.

## Optional local tools

`yt-dlp` and FFmpeg are optional user-installed executables. They are ignored
by Git and are not distributed in this repository. Their respective upstream
licenses apply when installed.
