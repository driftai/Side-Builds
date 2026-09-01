# New Features Engineering Contract

This branch is the staging line for the general media watch-party engine.

## Scope

The expansion beyond YouTube has two connected goals:

- generic external-media playback, including HLS/media URLs and host-authorized watch-page resolution
- lower-latency room replication using WebSocket, with SSE and short polling as fallbacks

The room domain remains provider- and transport-neutral. Providers resolve sources; playback adapters render sources; transports deliver authoritative room state.

## Source resolution contract

Only the current host may authorize a resolution job. Watch-page discovery is performed by the WatchParty server's isolated Playwright session, not by every viewer and not by forwarding the host's browser cookies/session. The resolver may observe normal browser-visible network requests, responses, media elements, and public metadata from a supplied public page. It returns candidate playable sources and metadata. The host selects one candidate; only the selected source is shared to the room.

Never make every viewer scrape the provider page. Never share resolver cookies, browser sessions, or private provider tokens through room state.

## Playback contract

Every provider maps onto the same room playback state:

`paused`, `ended`, `position`, `rate`, `updatedAt`, and authoritative server-time projection data.

Provider adapters own player-specific lifecycle details. They must not create separate room timelines or write synchronization policy into provider code.

## Realtime contract

WebSocket is preferred for state delivery. SSE remains a streaming fallback and HTTP polling is the final recovery path. A transport may fail or reconnect without changing playback semantics. Every authoritative room snapshot carries a monotonic `revision`; clients reject older snapshots.

Clients estimate server clock offset from bounded request/response samples and project playback against authoritative server time. Local `performance.now()` is used only as a monotonic local measurement, never as the shared cross-device clock. citeturn663841search1turn663841search3

## Testing gate

Every new provider/player adapter requires deterministic Node smoke coverage, browser/Playwright coverage, and an opt-in live check when an external service is involved. Realtime changes require protocol, multi-client, revision-ordering, reconnect, and fallback tests.

Live providers must never be required for the ordinary deterministic gate.

The local HLS runtime must be available through the project dependency tree; the browser must not depend on an unrelated runtime CDN to initialize external-media playback. HLS.js is installed as a pinned project dependency and served by WatchParty. citeturn663841search0turn175557search3

## Root-cause gate

A physical-device failure that automation misses becomes a regression target. Before another workaround is added, trace the actual state transition, transport, module-load order, event ownership, and final runtime owner. Fix the owning invariant and update the reproducer.

## Security gate

Resolver input must be public HTTP(S). DNS-resolved private, loopback, link-local, carrier-grade NAT, benchmarking, documentation, multicast, and other non-public destinations are rejected. Redirects and subresources are checked independently. Do not add DRM circumvention, credential/session extraction, encrypted provider-payload decryption, Cloudflare bot-evasion, or unrestricted fetching of private network targets. Playwright's route API supports aborting disallowed requests at the network boundary. citeturn663841search2turn663841search8

## Architecture gate

All new source modules remain under the hard 450-line ceiling. Entry points remain composition-focused. No provider or transport feature may recreate the monolith removed during the grand modularization.
