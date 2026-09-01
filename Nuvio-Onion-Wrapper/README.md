# Nuvio Onion Wrapper v17

Local browser wrapper for a **user-installed** NuvioTVSmart app. The Nuvio application itself is intentionally not part of this repository.

## Upstream Nuvio project

This wrapper works with the Nuvio TV web application project maintained by Nuvio Media:

**NuvioWeb — https://github.com/NuvioMedia/NuvioWeb**

The linked repository currently presents the Nuvio TV web application for Samsung Tizen and LG webOS and documents building the web application and TV packages from source. The repository identifies itself as the official Nuvio WebOS/TizenOS repository.

**Nuvio Onion Wrapper is a separate integration project.** It does not replace or redistribute the Nuvio application. Instead, it provides the local browser-facing wrapper, compatibility layer, addon proxy boundary, installation helpers, diagnostics, and launch flow needed to run a user-installed Nuvio build through the wrapper.

## Layout

The wrapper is self-contained and uses a path relative to its own folder by default: `./nuvio`.

That means the default Nuvio location is simply:

`Nuvio-Onion-Wrapper\\nuvio`

No assumption is made about where the parent `Nuvio-Onion-Wrapper` folder lives. It can be on Downloads, Desktop, another drive, a portable folder, or anywhere else.

You may keep Nuvio anywhere else on disk. Use one of these forms:

- `START_WRAPPER.bat "D:\Apps\Nuvio"`
- `GET_NUVIO.bat "D:\Apps\Nuvio"`
- `set NUVIO_PATH=D:\Apps\Nuvio`
- Copy `NUVIO_PATH.example.txt` to `NUVIO_PATH.txt` as a human-readable reminder (the launcher currently reads the environment variable or command-line path).

## First-time setup

1. Install or download the wrapper repository wherever you want.
2. Run `GET_NUVIO.bat` to download/install Nuvio into `./nuvio` inside that wrapper folder by default, or provide a custom path.
3. Run `START_WRAPPER.bat` (or pass the same custom Nuvio path).
4. Open `http://127.0.0.1:8797/`.

The wrapper builds/uses the Nuvio app in the user's selected local directory and serves only the generated browser build through the localhost wrapper.

## Why Nuvio is no longer committed here

The wrapper and Nuvio are intentionally separate projects. This keeps the public wrapper repository small, avoids redistributing the Nuvio source as part of the wrapper, and lets users control where their own Nuvio installation lives.

The public wrapper repository contains only the integration layer. A user's local Nuvio installation, dependencies, build output, and local configuration remain outside Git.

The `nuvio/` directory is a local installation location, not a copy of the upstream repository. A fresh checkout may contain only the tracked placeholder file there; the installer repairs or populates the directory when required.

## Browser compatibility changes

- Hides the outer wrapper status panel completely when there is no status text.
- Preserves the working QR/backend discovery configuration.
- Trailer playback remains user-initiated (no wrapper-forced Play).
- Keeps the YouTube browser trailer proxy compatibility layer.
- Proxies Stremio-compatible addon API calls (`manifest.json`, `catalog`, `meta`, `stream`, `subtitles`) through localhost to avoid browser CORS failures.
- Does not proxy the final media URL; stream URLs remain available to Nuvio's player as returned by addons.

The addon API proxy is restricted to public HTTPS hosts and approved addon API path families; localhost/private IP targets are rejected.

## Privacy and security

The wrapper is designed around a local-host boundary and a user-controlled Nuvio installation:

- Sensitive local credentials are not exposed to the browser runtime through the wrapper environment surface.
- HTTP serving is allow-listed so wrapper source/configuration files are not exposed as arbitrary static files.
- Path traversal outside the intended Nuvio browser-build directory is rejected.
- Outbound addon proxy requests require HTTPS and approved Stremio-compatible API paths.
- DNS-aware validation rejects private, loopback, link-local, multicast, and other non-public targets.
- Redirect destinations are revalidated before following them.
- Browser-provided cookies, authorization headers, origin, and referer are not forwarded through the public addon proxy.
- Unverified TLS fallbacks and generic unrestricted proxy routes are not used.

See `SECURITY.md` for the full containment model and regression checks.

## Diagnostics

- `SMOKE_TESTS.bat` / `smoke_tests.py`: local HTTP/build smoke tests.
- `BROWSER_SMOKE_TESTS.js`: DevTools inspection for detail-page input, focus, trailer layers, and pointer state.
- `AGY_AGENT_REPORT.md`: handoff instructions for a Google Antigravity CLI agent.
- `SECURITY.md`: public repository privacy/containment model.

## Upstream resources

- Nuvio Web application: https://github.com/NuvioMedia/NuvioWeb
- Nuvio website: https://nuvio.tv/
