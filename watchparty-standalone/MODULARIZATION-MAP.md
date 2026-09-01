# WatchParty Standalone — Grand Modularization Map

This is the implementation map for the first large modularization pass.

## Current problem

The project has accumulated substantial responsibilities inside the browser `public/app.js` and Node `server.js`. The new 450-line ceiling is intended to stop further growth and force coherent extraction.

The refactor must preserve the behavior already validated by the smoke suite: YouTube IFrame playback, room lifecycle, chat, host handoff, SSE/polling reconnect, LAN/sslip.io routing, Cloudflare Remote mode, audio preferences, late join state, and adaptive playback synchronization.

## Target browser layout

`public/app.js`

Thin browser composition root only. It should initialize the client application and connect the modules below. It should not contain the detailed implementations of networking, session storage, YouTube player lifecycle, sync math, or large render/event blocks.

`public/modules/client-state.js`

Own client-side room/session state, member identity, room/session persistence, host checks, and state transitions.

`public/modules/storage.js`

Own localStorage-safe access, client/account identity, persisted name/session/audio preferences, and browser-safe fallbacks.

`public/modules/transport.js`

Own API URL construction, network-info discovery, SSE connection management, remote polling, reconnect behavior, heartbeat, and connection status transitions.

`public/modules/room-api.js`

Own create/join/leave/command requests and response normalization. Keep HTTP details out of UI/player code.

`public/modules/youtube.js`

Own YouTube IFrame API loading, player creation, player lifecycle, autoplay priming, video identity, YouTube error handling, and audio preference restoration.

`public/modules/playback-sync.js`

Own authoritative timeline projection, drift measurement, adaptive rate correction, hard-sync threshold/cooldown, manual sync, and synchronization diagnostics.

`public/modules/room-ui.js`

Own DOM rendering, room/member/chat presentation, status labels, source input state, copy/share actions, and UI event wiring.

`public/modules/network-links.js`

Own LAN/sslip.io/local/remote share-link generation and canonical URL decisions.

## Target server layout

`server.js`

Thin composition/bootstrap root. It should load configuration, construct the application/server, register routes, start listening, and perform minimal process-level wiring.

`server/config.js`

Port, host, LAN mode, TTLs, constants, and runtime configuration.

`server/network.js`

Network-interface discovery, physical-vs-virtual adapter classification, LAN URL generation, canonical local/LAN hosts, and network-info payload creation.

`server/rooms.js`

Room creation, room lookup/aliases, room state, member/session lifecycle, host ownership/handoff, messages, and room cleanup.

`server/playback.js`

YouTube source normalization, playback state model, projected timeline calculation, and playback command/domain validation.

`server/http.js`

HTTP helpers, JSON responses, request-body parsing, CORS policy, static file serving, and canonical navigation redirects.

`server/routes/rooms.js`

Room REST endpoints: create, join, state, ping, leave, command, and delete behavior. Routes should delegate to domain/services instead of storing business logic inline.

`server/routes/events.js`

SSE endpoint, stream registration/removal, event broadcasting, and heartbeat comments.

`server/lifecycle.js`

Periodic stale-member cleanup, empty-room expiry, deleted-room tombstone cleanup, and process lifecycle helpers.

## Dependency direction

Browser:

`app.js -> room-ui / transport / room-api / youtube / playback-sync / client-state / network-links`

Player and synchronization modules should not know about DOM selectors except through small adapters supplied by the composition root.

Server:

`server.js -> routes/http/lifecycle -> rooms/playback/network -> low-level helpers`

Domain modules must not depend on Node HTTP response objects or browser globals.

Avoid cycles. Shared behavior belongs in a lower-level module rather than creating bidirectional imports.

## Extraction order

Use this order to keep behavior safe:

1. Extract pure helpers/constants and network-link logic.
2. Extract YouTube player lifecycle.
3. Extract playback synchronization and leave its existing tested behavior unchanged.
4. Extract transport/reconnect logic.
5. Extract session/storage and room API helpers.
6. Extract UI rendering/event wiring.
7. Reduce `public/app.js` to a composition root.
8. Extract server network/config helpers.
9. Extract room/domain state.
10. Extract playback/source domain logic.
11. Extract HTTP/static helpers.
12. Split room REST and SSE routes.
13. Extract lifecycle cleanup.
14. Reduce `server.js` to a composition root.

After each coherent extraction, run the smallest affected regression ring. At the end, run the full verification suite plus architecture gate.

## Non-negotiable preservation rules

- No feature behavior should be changed merely to make extraction easier.
- Do not reintroduce the old 5-second forced seek loop.
- Preserve adaptive playback drift correction.
- Preserve the 120-second stale-member grace period.
- Preserve 1-second fallback polling.
- Preserve SSE heartbeats.
- Preserve physical LAN `sslip.io` canonicalization.
- Preserve the local-only `tools/cloudflared.exe` dependency model.
- Do not commit `.runtime` or local executables.
- Preserve the live YouTube IFrame integration test.
- Preserve the low-noise/change-aware smoke architecture.

## Acceptance criteria

The grand modularization is complete when:

1. `npm run test:architecture` passes with no normal source module over 450 lines.
2. `public/app.js` and `server.js` are composition-focused rather than logic monoliths.
3. The browser and server module graph has no avoidable circular dependencies.
4. Existing deterministic Node smokes pass.
5. Existing Playwright tests pass.
6. Playback-drift regression passes.
7. Live YouTube iframe smoke passes when enabled.
8. LAN/sslip.io/Cloudflare integration checks remain valid.
9. A real local WatchParty session still works.
10. Astro leaves the local checkout synchronized to the exact tested GitHub SHA.

## Future feature rule

Before adding a new feature, identify its owning module. If no existing module has a single clear responsibility for it, create a new module rather than extending an already-large file.

A pull/commit that adds a feature while knowingly increasing an oversized file is considered incomplete until the responsibility is extracted.
