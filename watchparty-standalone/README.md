# WatchParty Standalone — General Media Watch-Party Engine

A lightweight personal watch-party server with authoritative room state, synchronized playback, chat, LAN/remote sharing, YouTube playback, and host-authorized external media discovery.

## Upstream project

Related upstream project:

**WatchParty — https://github.com/howardchung/watchparty**

The upstream WatchParty project is a separate, broader watch-together website with synchronized playback, rooms, chat, YouTube, HLS, internet video files, and additional features.

**WatchParty Standalone is a separate implementation.** It does not require the upstream application to run. This project focuses on a small standalone local/LAN/remote server with a provider-neutral playback architecture and an explicit security boundary around external-media resolution.

## Playback architecture

WatchParty has a provider-neutral room/playback layer. YouTube is one provider; external HLS and media-file sources use the browser's HTML media element, with hls.js used when the browser does not provide native HLS support.

The room server owns the authoritative source and playback timeline. Providers own player-specific lifecycle details. Transports deliver the same room snapshot and must never create a second playback timeline.

## YouTube

The YouTube path uses the official YouTube IFrame Player API. The input accepts YouTube watch URLs, youtu.be links, Shorts, live URLs, embed URLs, or a video ID. YouTube lifecycle events remain owned by the YouTube player adapter, while the server remains authoritative for shared play/pause/seek/rate state.

## External media

The External Media input supports two forms:

1. A direct playable `.m3u8`, `.mp4`, `.webm`, `.ogg`, or `.mov` URL.
2. A public watch-page URL that can be inspected by an isolated host-authorized Playwright session on the WatchParty server.

Only the current room host may authorize discovery. The server-side resolver observes normal browser-visible requests/responses and media elements from the public page, then returns candidate playable sources. The host chooses one candidate. Only the selected final playable URL and non-sensitive metadata are written into room state and shared with viewers.

The discovery UI can surface:

- title
- server/host label when observable
- provider label when observable
- sub/dub classification when observable
- quality when observable
- subtitle track URLs when observable
- direct HLS/media URL

Viewers do not repeat provider discovery and do not receive the resolver browser session, cookies, or private credentials.

### Miruro-like pages

Generic browser-visible discovery is intended to work with pages that expose their playable source to a normal browser session. WatchParty intentionally does not implement protected-pipe decryption, DRM circumvention, credential extraction, or Cloudflare bot-evasion; pages that hide their playable media behind those mechanisms may remain unresolved.

## Realtime transport

Transport priority is:

1. WebSocket — preferred low-latency room updates.
2. Server-Sent Events — streaming fallback.
3. Short HTTP polling — final recovery path.

All three transports consume the same room store and authoritative playback state. Every room snapshot includes a monotonic revision and authoritative server time. Clients reject stale revisions and use bounded server-clock estimation for timeline projection. Browser `performance.now()` remains a local monotonic clock rather than a shared cross-device clock.

The WebSocket server uses `ws` with a bounded payload and compression disabled for the small room-state messages. Compression can add CPU and memory overhead for this workload.

## HLS runtime

HLS.js is pinned as a project dependency and served locally at `/vendor/hls.js`. External-media playback therefore does not depend on a third-party runtime CDN being reachable from every viewer device.

## LAN / remote access

The project can listen on `0.0.0.0:9085` for LAN mode. Remote mode uses the local user-installed `tools\\cloudflared.exe` binary. The executable remains outside Git and is never automatically downloaded or replaced by WatchParty.

## Room behavior

Rooms can use human numeric aliases such as `123`. The server maps those aliases to an internal room ID while keeping the user-facing join code stable.

The host is authoritative for source and playback control. Viewers receive the latest source and projected position before their player is synchronized.

## Testing

The project uses a low-noise test ring with architecture enforcement plus Node and Playwright regression coverage.

### Fast deterministic checks

`npm run test:architecture`

`npm run test:smoke`

`npm run test:browser`

`npm test`

### Live checks

`npm run test:youtube-live`

`npm run test:media-live` with `LIVE_MEDIA_URL` set to a direct playable HLS/media URL.

`npm run test:media-page-live` with `LIVE_MEDIA_PAGE_URL` set to a public watch-page URL.

Live provider checks are opt-in and are never required for the ordinary deterministic suite.

### Regression coverage

The browser suite covers room creation/join, host/viewer playback, repeated terminal replay behavior, external-media UI, WebSocket transport, SSE fallback, and the existing YouTube regressions.

The Node suite covers room/media authorization, direct URL classification, provider selection, browser-backed media resolution against deterministic fixtures, WebSocket join/broadcast, monotonic revisions, authoritative server-time ping, and playback state-machine invariants.

## Architecture rules

Every source module must remain under the hard 450-line ceiling. `server.js` and `public/app.js` remain composition roots rather than feature containers.

A real-device failure that automation misses becomes a regression target. Before another workaround is added, trace authoritative state -> transport -> client -> final runtime owner, look for duplicate listeners/module replacement/guards, fix the owning invariant, and strengthen the reproducer.

A provider or transport must never create its own room timeline. Synchronization helpers must not replace the lifecycle owner.

## Security boundary

Resolver input is public HTTP(S). Initial destinations and browser subrequests are validated against public address requirements; loopback, private, link-local, carrier-grade NAT, benchmarking, documentation, multicast, and related non-public targets are rejected. Public-mode host-management and network diagnostics are kept separate from player-facing endpoints. Do not add DRM circumvention, credential/session extraction, encrypted provider-payload decryption, Cloudflare bot-evasion, or unrestricted fetching of private network targets.

## Project documents

- `NEW-FEATURES.md` — branch engineering contract
- `MEDIA-PROVIDERS.md` — source/provider contract
- `REALTIME.md` — transport architecture
- `EXTERNAL-MEDIA-NOTES.md` — external-media implementation notes
- `MODULARIZATION.md` — architecture and root-cause repair rules
- `LAST-VERIFICATION.md` — compact Astro verification relay
