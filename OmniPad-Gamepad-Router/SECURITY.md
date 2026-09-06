# OmniPad Security & Privacy Model

## Scope

This document describes the security boundary for the OmniPad Gamepad Router. It is designed so a remote player can control a virtual gamepad through the `/play` WebSocket without gaining host-management privileges or receiving unnecessary host-machine metadata.

## Public Cloudflare sessions

Cloudflare Quick Tunnel URLs expose the player surface intentionally. A valid room code acts as the session bearer secret for joining a slot. Anyone who obtains both the public tunnel URL and room code can attempt to join that room, so the link and code must be treated as private session credentials.

Public tunnel clients can:

- load `/play` / `/join`;
- read controller profiles;
- connect to `/ws/player` and submit input for a valid room/slot.
- as the authoritative slot owner, request best-effort focus of the exact target the host already selected.

Public tunnel clients cannot use host management endpoints.

## Host-management boundary

The host dashboard and management APIs are local/private-network only. The following are not available through a Cloudflare public session:

- host dashboard `/`;
- `/ws/host` telemetry/control channel;
- target enumeration and selection;
- tunnel start/stop/status;
- controller, SOCD, deadzone, mute, reset, kick, and panic controls;
- native background keyboard helper lifecycle/status APIs.

Remote `/api/status` is intentionally reduced to non-sensitive session/application information. Remote `/api/target/status` omits process IDs, executable paths, window titles, and other host-window identity details.

The player `focus_target` message cannot choose a PID, HWND, path, or title. Observers and unattached sockets are rejected, requests are rate-limited, and the response exposes only a generic result reason. Windows can still deny the foreground request.

## No process injection

Target selection is implemented through normal Windows window/process enumeration. OmniPad does not inject DLLs or patch game memory.

## Local background keyboard helper

The native helper is explicitly a host-side feature. It is only startable from a directly connected local/private client and uses the server's loopback WebSocket endpoint. The helper is not enabled by a public Cloudflare browser request.

## Repository hygiene

Secrets and local credentials should never be committed. The repository `.gitignore` excludes environment files, keys, credentials, Cloudflare state, logs, virtual environments, and runtime state.

The default room code is generated randomly for each server run unless an explicit `--code` is supplied. For a public session, use a fresh explicit code or let OmniPad generate one rather than reusing a predictable code.

## Containment note

OmniPad can intentionally create local virtual input devices and inspect running Windows windows because those are core features. The security goal is containment: those capabilities stay on the host, while public clients receive only the player input channel and deliberately minimal status data.

## Public-repository readiness

The source tree is suitable for publication provided maintainers continue to avoid committing secrets or real session URLs/codes. Public deployment remains a link-and-room-code trust model rather than authenticated multi-user access control. For untrusted/public game rooms, stronger authentication and rate limiting should be added before treating the service as an open public service.
