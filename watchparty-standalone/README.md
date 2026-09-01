# WatchParty Standalone — General Media Watch-Party Engine

A lightweight standalone watch-party server for watching media together with synchronized playback, chat, LAN/remote sharing, YouTube, direct HLS/media sources, and host-authorized public watch-page media discovery.

## What this project is

**WatchParty Standalone is an independent implementation.** It is not a fork or bundled copy of the upstream WatchParty application.

Upstream reference:

**WatchParty — https://github.com/howardchung/watchparty**

The upstream project is a broader watch-together website with synchronized playback, rooms, chat, YouTube, HLS, screen sharing, video chat, and additional features. WatchParty Standalone instead focuses on a compact local/LAN/remote server, a provider-neutral playback engine, and an explicit security boundary around external-media discovery. citeturn264313search0

## Features

- Authoritative room playback state shared across all viewers.
- WebSocket realtime transport with SSE and short polling recovery paths.
- YouTube playback through the official YouTube IFrame Player API.
- Direct `.m3u8`, `.mp4`, `.webm`, `.ogg`, and `.mov` playback.
- Public watch-page discovery through a host-authorized isolated Playwright session.
- Candidate stream selection with optional quality, provider/server, sub/dub, and subtitle metadata when observable.
- LAN mode and optional Cloudflare Quick Tunnel remote sharing.
- Room aliases and ephemeral in-memory room state.
- Host-authoritative playback controls and bounded clock/drift correction.
- Locally served HLS.js runtime so viewers do not depend on a third-party HLS CDN.
- Responsive browser client suitable for local computers and remote devices.

## Playback architecture

The server owns the authoritative room source and playback timeline. Provider adapters own provider-specific player lifecycle details, while WebSocket/SSE/polling transports distribute the same authoritative state.

No provider or transport is allowed to create a second room timeline. Clients use monotonic revisions and bounded server-clock estimation to reject stale snapshots and project playback locally.

## YouTube

The YouTube path accepts watch URLs, `youtu.be` links, Shorts, live URLs, embed URLs, and video IDs. YouTube player lifecycle events remain owned by the YouTube adapter while the server remains authoritative for shared play/pause/seek/rate state.

## External media

External Media accepts:

1. A direct playable `.m3u8`, `.mp4`, `.webm`, `.ogg`, or `.mov` URL.
2. A public watch-page URL inspected by an isolated host-authorized Playwright session.

Only the room host may authorize discovery. The resolver observes normal browser-visible requests/responses and media elements, then returns candidate playable sources for the host to choose from.

The discovery UI can surface information such as title, provider/server label, sub/dub classification, quality, subtitles, and a final playable media URL when those values are observable from the public page.

Viewers do not receive the resolver browser session, cookies, or private credentials.

### Miruro-like watch pages

The generic resolver is intended for public pages that expose playable media to a normal browser session. Some public Miruro-derived projects expose HLS manifests and subtitles through provider APIs; this implementation intentionally does **not** perform DRM circumvention, encrypted-payload decryption, credential/session extraction, or Cloudflare bot-evasion. Pages protected by those mechanisms may remain unresolved.

## Realtime transport

Transport priority is:

1. **WebSocket** — preferred low-latency room updates.
2. **Server-Sent Events** — streaming fallback.
3. **Short HTTP polling** — final recovery path.

All three consume the same authoritative room state. Room snapshots contain a monotonic revision and authoritative server time, and clients reject stale revisions before applying state.

The WebSocket server uses bounded payloads and keeps compression disabled for the small room-state messages used by this project.

## HLS runtime

HLS.js is pinned as a project dependency and served locally at `/vendor/hls.js`. This keeps playback from depending on a third-party runtime CDN being reachable from every viewer device.

## LAN and remote access

LAN mode can listen on `0.0.0.0:9085` for cross-device local-network access.

Remote mode uses a **user-installed** `tools\\cloudflared.exe` binary to create a temporary Cloudflare Quick Tunnel. The executable and runtime tunnel state are not committed to Git and are not automatically replaced by the application.

Public/tunnel mode is intentionally separated from host-management functionality. Network diagnostics and host-only controls remain local-only.

## Room behavior

Rooms may use human-friendly numeric aliases. The server maps aliases to internal room IDs while keeping the user-facing join code stable.

The current room host is authoritative for source and playback control. Viewers receive the latest source and projected playback position before synchronization.

Room state is intentionally ephemeral and held in memory rather than persisted as a permanent media database.

## Privacy and security boundary

WatchParty Standalone is designed to keep the server's local machine separate from remote viewers.

- Host network diagnostics are not exposed through the public tunnel.
- Public room state uses sanitized/opaque identifiers instead of internal account identifiers.
- Session resume is identity-bound rather than trusting a member identifier alone.
- Static file serving is explicitly contained inside the `public/` directory.
- External media destinations are restricted to public HTTP(S) targets.
- Loopback, RFC1918/private, link-local, carrier-grade NAT, multicast, benchmarking, documentation, and related non-public destinations are rejected.
- Hostnames are DNS-resolved and their resolved addresses are checked before outbound access.
- Redirect destinations are revalidated before following them.
- Browser cookies, authorization headers, `Origin`, and `Referer` are not forwarded through the public addon/media proxy paths.
- Host-management endpoints remain separated from player-facing endpoints in public mode.
- No DRM circumvention, credential extraction, unrestricted private-network fetching, or Cloudflare bot-evasion is implemented.

See `SECURITY.md` for the complete containment model and security regression coverage.

## Testing

The project uses a low-noise test ring with architecture enforcement, Node smoke/security coverage, and Playwright browser regression tests.

### Common deterministic checks

`npm run test:architecture`

`npm run test:smoke`

`npm run test:browser`

`npm test`

### Optional live checks

`npm run test:youtube-live`

`npm run test:media-live` with `LIVE_MEDIA_URL` set to a direct playable HLS/media URL.

`npm run test:media-page-live` with `LIVE_MEDIA_PAGE_URL` set to a public watch-page URL.

Live provider checks are opt-in and are not required for the ordinary deterministic suite.

### Security regression coverage

The regression suite covers:

- public/tunnel denial of host network diagnostics
- sanitized public room state
- session identity mismatch rejection
- static-path traversal variants
- media-stream SSRF boundaries
- redirect-based SSRF protection
- WebSocket/SSE transport behavior
- room authorization and host/viewer permissions
- monotonic revision and server-time behavior
- playback state-machine invariants

## Current verification

The latest promoted build has been verified with the full WatchParty smoke/browser/security ring used during the Side-Builds promotion. The final Astro verification reported **56/56 checks passed**, including architecture, Node smoke/security, browser E2E, realtime transport, playback consistency, media resolution, and security boundary coverage.

Live external-network cases may be skipped when their opt-in environment variables are not configured.

## Architecture rules

Every normal source module must remain under the hard **450-line** ceiling. `server.js` and `public/app.js` are composition roots rather than feature containers.

Real-device failures should become regression targets. Before adding another workaround, trace authoritative state -> transport -> client -> final runtime owner, identify duplicate listeners/module replacement/guard problems, fix the owning invariant, and add the reproducer to the test ring.

## Project documents

- `NEW-FEATURES.md` — branch engineering contract
- `MEDIA-PROVIDERS.md` — source/provider contract
- `REALTIME.md` — transport architecture
- `EXTERNAL-MEDIA-NOTES.md` — external-media implementation notes
- `MODULARIZATION.md` — architecture and root-cause repair rules
- `SECURITY.md` — privacy and containment model
- `LAST-VERIFICATION.md` — compact verification relay
