# Nuvio Onion Wrapper v17

A local browser-facing compatibility wrapper for a **user-installed Nuvio TV web application**. The Nuvio application itself is intentionally not committed to this repository.

## Upstream project

This wrapper integrates with the Nuvio TV web application maintained by Nuvio Media:

**NuvioWeb — https://github.com/NuvioMedia/NuvioWeb**

NuvioWeb is the upstream Nuvio TV web application for Samsung Tizen, LG webOS, and normal browser-based development. Its current repository documents TV packaging, desktop installation, playback, and integration with the Stremio addon ecosystem. citeturn264313search1turn264313search5

**Nuvio Onion Wrapper is a separate integration project.** It does not replace the upstream application and does not redistribute the upstream source. It provides a local wrapper, compatibility layer, controlled addon proxy, installation helpers, diagnostics, and launch flow around a Nuvio build installed by the user.

## What the wrapper provides

- Local browser access to a user-installed Nuvio build.
- Wrapper-relative default installation at `./nuvio`.
- Optional custom Nuvio installation paths.
- Launcher and installer/repair scripts for first-time setup.
- Browser compatibility fixes around the Nuvio UI/runtime.
- Controlled Stremio-compatible addon API proxying to avoid browser CORS limitations.
- YouTube trailer compatibility behavior without forcing playback.
- QR/backend discovery preservation.
- Local diagnostics and smoke-test tooling.
- Security controls around outbound addon requests, redirects, DNS resolution, TLS, and filesystem exposure.

## Installation location

The wrapper never assumes a specific parent directory such as `Downloads\\Private-Test-Builds`.

By default, the Nuvio installation lives relative to the wrapper itself:

`Nuvio-Onion-Wrapper\\nuvio`

That means the wrapper can be placed on Downloads, Desktop, another drive, a portable disk, or another directory without changing the default path.

A custom installation location is also supported, for example:

- `START_WRAPPER.bat "D:\Apps\Nuvio"`
- `GET_NUVIO.bat "D:\Apps\Nuvio"`
- `set NUVIO_PATH=D:\Apps\Nuvio`

## First-time setup

1. Clone or copy this wrapper anywhere on the computer.
2. Run `GET_NUVIO.bat` to install/populate the selected Nuvio directory, using `./nuvio` by default.
3. Run `START_WRAPPER.bat`.
4. Open `http://127.0.0.1:8797/`.

The installer validates the actual Nuvio files it needs. An empty or incomplete `nuvio/` directory is treated as an installation that needs repair rather than as a valid installation merely because the directory exists.

## External-Nuvio architecture

The actual Nuvio installation is **user-side data**.

The public Git repository contains only the wrapper/integration project and a placeholder for the default `nuvio/` location. The real Nuvio source, dependencies, generated `dist/` output, local configuration, and other installation data remain outside Git.

A valid local Nuvio installation is preserved when the wrapper is updated. Normal Git pulls, rebases, branch switches, commits, and pushes must not upload, replace, or clear the user's installed Nuvio files.

The repository's `nuvio/` tree is therefore expected to contain only its tracked placeholder in a fresh checkout; installation scripts populate it locally when required.

## Browser compatibility layer

The wrapper currently includes compatibility behavior for:

- hiding the outer wrapper status panel when it has no meaningful status text
- preserving QR/backend discovery configuration
- keeping trailer playback user-initiated rather than forcing Play
- retaining YouTube trailer proxy compatibility behavior
- proxying supported Stremio-compatible addon API paths (`manifest.json`, `catalog`, `meta`, `stream`, `subtitles`) through the local wrapper to avoid browser CORS failures
- leaving final media URLs to Nuvio's player rather than turning the wrapper into a generic media proxy

The addon proxy is intentionally limited to approved public HTTPS hosts and supported Stremio API path families.

## Privacy and security boundary

The wrapper is designed around a local-host boundary and a user-controlled Nuvio installation.

- Sensitive local credentials are not exposed through the browser runtime environment surface.
- Wrapper source and configuration files are not exposed as arbitrary static files.
- Static child paths are explicitly contained within the intended browser-build root.
- Path traversal attempts are rejected.
- Outbound addon requests require HTTPS and approved Stremio-compatible paths.
- DNS resolution is checked so hostnames resolving to loopback, private, link-local, multicast, or other non-public addresses are blocked.
- Redirect destinations are revalidated before being followed.
- Incoming browser cookies, authorization headers, `Origin`, and `Referer` are not forwarded through the public addon proxy.
- Unverified TLS fallbacks are not used.
- Generic unrestricted proxy endpoints are not exposed.
- Host filesystem paths and sensitive installation diagnostics are redacted from public responses.

See `SECURITY.md` for the full containment model and security regression suite.

## Git safety for user installations

The local `nuvio/` installation is deliberately protected from repository operations.

The intended Git state is:

- real Nuvio application files: **not tracked**
- `nuvio/.gitkeep`: tracked placeholder only
- local installed Nuvio files: ignored
- `git add -A`: must not stage user Nuvio data
- `git push`: must never contain the user's Nuvio installation

This separation lets users keep their Nuvio installation in the default wrapper-relative directory while updating the wrapper independently.

## Testing

The wrapper uses a combined functional and security verification ring.

### Security tests

`python tests/test_security.py`

Coverage includes:

- private/loopback target rejection
- DNS-aware public-target validation
- HTTPS and approved Stremio API path enforcement
- browser runtime credential redaction
- filesystem surface allow-listing
- path-traversal containment
- wrapper-relative Nuvio path behavior
- empty/incomplete installation detection and repair conditions
- Git placeholder separation
- arbitrary proxy/TLS downgrade protections

### Smoke tests

`python smoke_tests.py`

The smoke suite verifies wrapper startup, required Nuvio build files, safe HTTP surfaces, runtime environment redaction, proxy restrictions, filesystem diagnostics, public addon connectivity, and Nuvio metadata/runtime compatibility.

### Current verification

The promoted public build was verified during migration with:

- **10/10 security checks passed**
- **17/17 functional smoke checks passed**
- user-side external Nuvio installation validated successfully
- secret/history scan clean during promotion

## Upstream resources

- Nuvio Web application: https://github.com/NuvioMedia/NuvioWeb
- Nuvio website: https://nuvio.tv/

## Project documents

- `SECURITY.md` — privacy, credential, network, proxy, and filesystem boundaries
- `SMOKE_TESTS.bat` — Windows smoke-test launcher
- `smoke_tests.py` — functional and security smoke suite
- `tests/test_security.py` — security regression suite
- `NUVIO_PATH.example.txt` — custom-path reminder

## License / upstream note

This wrapper is a separate integration layer. Review the licenses and terms of the upstream Nuvio project and any addons or media sources you choose to use. The wrapper itself does not grant rights to third-party content or services.
