# WatchParty Standalone — Realtime Transport

## Transport hierarchy

1. WebSocket (`/ws`) is the preferred room-state transport for low-latency updates.
2. Server-Sent Events remains the streaming fallback.
3. Short HTTP polling is the final recovery path for networks/proxies that cannot hold a stream.

All transports carry the same authoritative room state. Changing transport must never create a second room backend or a second playback timeline.

## Server authority

The Node room store owns membership, host identity, source, playback state, chat, lifecycle, and a monotonic room revision. Every authoritative state broadcast increments the revision. Clients reject older snapshots so delayed fallback responses cannot rewind newer state.

Room snapshots also carry authoritative server epoch time. Clients estimate server clock offset using request midpoint samples and use that estimate for playback projection. `performance.now()` remains a local monotonic timer; it is not a shared cross-device clock because browser time origins differ. citeturn663841search1turn663841search3

## WebSocket lifecycle

A client connects to `/ws`, sends one `join` message with its existing `roomId` and `memberId`, receives an initial state, then receives broadcast state updates. The server uses ping/pong heartbeats and a bounded message payload. The browser uses limited reconnect backoff and falls back to SSE/polling if WebSocket negotiation is unavailable.

The fallback hierarchy is exclusive: when one transport becomes authoritative for delivery, the previous transport is closed. A client must not consume the room through simultaneous WebSocket + SSE + polling channels.

## Remote mode

Cloudflare Quick Tunnel remains supported. WebSocket is attempted first because the browser/server path is already the same room backend. If the proxy cannot sustain WebSocket, the client falls back without changing room state or playback semantics.

## Sync invariants

- host PLAY/PAUSE/SEEK/RATE is authoritative
- viewer drift correction never replaces lifecycle ownership
- terminal `ENDED` is an explicit state
- replay clears terminal state and resets the authoritative timeline
- transport reconnection converges to the newest room revision
- server-time projection is preferred over receipt-time projection
- no periodic forced seek loop is permitted

## Testing

Realtime changes require:

- Node WebSocket join and initial-state smoke
- Node broadcast-to-WebSocket smoke
- monotonic revision smoke
- Playwright host/viewer realtime connection smoke
- stale-snapshot rejection coverage
- reconnect/fallback tests
- existing playback drift and replay regressions
- LAN and remote integration checks

The WebSocket layer should remain replaceable. A provider or transport implementation must not embed application state into the transport itself.
