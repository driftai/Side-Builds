# Nuvio Onion Wrapper v17

Local browser wrapper for a **user-installed** NuvioTVSmart app. The Nuvio source is not part of this repository.

## Layout
The wrapper is self-contained and uses a path relative to its own folder by default: `./nuvio`.

That means the default Nuvio location is simply:

`Nuvio-Onion-Wrapper\nuvio`

No assumption is made about where the parent `Nuvio-Onion-Wrapper` folder lives. It can be on Downloads, Desktop, another drive, a portable folder, or anywhere else.

You may keep Nuvio anywhere else on disk. Use one of these forms:

- `START_WRAPPER.bat "D:\Apps\Nuvio"`
- `GET_NUVIO.bat "D:\Apps\Nuvio"`
- `set NUVIO_PATH=D:\Apps\Nuvio`
- Copy `NUVIO_PATH.example.txt` to `NUVIO_PATH.txt` as a human-readable reminder (the launcher currently reads the environment variable or command-line path).

## First-time setup
1. Install or download the wrapper repository wherever you want.
2. Run `GET_NUVIO.bat` to download Nuvio into `./nuvio` inside that wrapper folder by default, or provide a custom path.
3. Run `START_WRAPPER.bat` (or pass the same custom Nuvio path).
4. Open `http://127.0.0.1:8797/`.

The wrapper builds/uses the Nuvio app in the user's selected local directory and serves only the generated `dist` browser build through the localhost wrapper.

## Why Nuvio is no longer committed here
The wrapper and Nuvio are intentionally separate projects. This keeps the public wrapper repository small, avoids redistributing the Nuvio source as part of the wrapper, and lets users control where their own Nuvio installation lives.

The public wrapper repository contains only the integration layer. A user's local Nuvio installation, dependencies, build output, and local configuration remain outside Git.

## Browser compatibility changes
- Hides the outer wrapper status panel completely when there is no status text.
- Preserves the working QR/backend discovery configuration.
- Trailer playback remains user-initiated (no wrapper-forced Play).
- Keeps the YouTube browser trailer proxy compatibility layer.
- Proxies Stremio-compatible addon API calls (`manifest.json`, `catalog`, `meta`, `stream`, `subtitles`) through localhost to avoid browser CORS failures.
- Does not proxy the final media URL; stream URLs remain available to Nuvio's player as returned by addons.

The addon API proxy is restricted to public HTTPS hosts and the addon API path families above; localhost/private IP targets are rejected.

## Diagnostics
- `SMOKE_TESTS.bat` / `smoke_tests.py`: local HTTP/build smoke tests.
- `BROWSER_SMOKE_TESTS.js`: DevTools inspection for detail-page input, focus, trailer layers, and pointer state.
- `AGY_AGENT_REPORT.md`: handoff instructions for a Google Antigravity CLI agent.
- `SECURITY.md`: public repository privacy/containment model.
