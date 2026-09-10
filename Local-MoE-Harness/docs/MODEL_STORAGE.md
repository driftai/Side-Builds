# Model Storage Locations

Local MoE Harness can keep its application/runtime files in one location while model weights live somewhere else.

## Goals

- Keep large checkpoints off the drive that contains the Harness when space is limited.
- Keep rarely used models on removable or external storage.
- Allow different registered models to live on different volumes.
- Preserve the trusted model registry: changing a location does not turn an arbitrary checkpoint into a supported model definition.
- Keep machine-specific paths out of Git and public configuration.

## How locations work

Each model still has a trusted default location from `config/models.json`, normally below `models/` in the Harness directory.

A user can override that location from the browser's **Change model → Model storage locations** section. The override is stored only in:

```text
state/model-locations.json
```

`state/` is runtime state and is ignored by Git. Absolute user paths must never be added to `config/models.json` for a public release.

The linked path may point to:

- another local drive;
- a user-accessible mounted volume;
- WSL-visible storage when the selected host/runtime can actually read that path;
- removable/external storage.

For normal multi-file models, link the directory containing the model's required files. For a single-file registered GGUF model, either its containing directory or the exact registered GGUF file may be linked.

## Storage performance

External model locations are a capacity and organization feature; they do not guarantee identical I/O performance on every filesystem.

Keep performance-sensitive model weights on a filesystem that is native to the process reading them when practical. In particular, a native Windows runtime reading model weights from a WSL Linux filesystem through `\\wsl$`, `\\wsl.localhost`, or a mapped drive backed by those paths may have more filesystem overhead than reading the same weights from NTFS. Likewise, Linux tools generally perform best with Linux-side files rather than repeatedly crossing into a mounted Windows filesystem.

When choosing a cross-OS or removable location, validate the exact setup with a real model startup and a short generation/benchmark before deleting the previous copy. If capacity matters more than startup/I/O speed, a slower external location can still be a useful tradeoff.

## Removable/offline models

A linked path does not have to remain online permanently. If an external drive is disconnected, the Harness remembers the path but marks the model unavailable/not installed. Reconnect the drive and refresh the model panel before switching to it.

The Harness does not silently copy model weights back into its own directory.

## Changing a location

Filesystem-location editing is allowed only from a loopback/local browser session. Remote clients do not receive the absolute model paths through `/api/models` and cannot change the model-location state.

If the model is currently running under the Harness-managed FreeToken runtime, stop the runtime before changing that model's path. This avoids moving or relinking checkpoint files while the inference process may still be using them.

## Moving an existing model safely

1. Stop the Harness-managed FreeToken runtime.
2. Move or copy the complete checkpoint directory to its new location.
3. Open the Harness locally.
4. Open **Change model → Model storage locations**.
5. Paste the new absolute path for the matching registered model and choose **Link path**.
6. Confirm the model shows **Checkpoint ready**.
7. Start/switch to the model and run a small generation smoke test.
8. Delete the old duplicate only after the new location has passed the smoke test.

For removable storage, keep the saved link even while the drive is disconnected; the model will become available again when the path returns.

## Browser path selection

The UI intentionally accepts a server-side absolute path as text instead of depending on a browser directory picker. Browser filesystem APIs return permission-scoped handles and do not provide a portable server filesystem path that a separate local Python process can reliably reuse across platforms.

## Security boundary

Location overrides change only where a **known registry model** is loaded from. They do not allow callers to define arbitrary model IDs, launch commands, architectures, runtime flags, or served model identities. Registry validation and platform compatibility rules still apply.
