# Server Modules

This directory contains focused Node-side modules. Keep the repository-root `server.js` as a thin composition/bootstrap entrypoint.

Planned responsibilities are documented in `../MODULARIZATION-MAP.md`:
configuration, network discovery, room/domain state, playback/source domain logic, HTTP/static helpers, room routes, SSE routes, and lifecycle cleanup.

Do not create a new catch-all server module. New functionality must have a clear owner and stay below the 450-line source ceiling.