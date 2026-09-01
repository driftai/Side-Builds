# Node Smoke Layer

Reserved for deterministic server/API smoke tests.

Astro: inspect `server.js` first, identify the actual routes and lifecycle, then implement small tests here. Prefer an isolated local server instance and ephemeral room/test data. Avoid network-dependent assertions.