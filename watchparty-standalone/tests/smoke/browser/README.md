# Playwright Browser Smoke Layer

Reserved for Playwright end-to-end tests against the real WatchParty UI.

Core scenarios: lobby render, room creation/join, host/viewer contexts, room-link navigation, chat, source loading and ready state, play/pause/seek synchronization, late join state, connection/reconnect behavior, and regression coverage preventing the old continuous 5-second forced-seek behavior.

Astro: configure Playwright to launch/manage the local WatchParty server where practical. Capture screenshots and traces on failures. Keep live YouTube dependence out of the deterministic baseline suite.