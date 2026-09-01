# External media implementation notes

The new-features branch introduces a provider-neutral media path beside YouTube.

The host can provide either a direct HLS/media URL or a public watch-page URL. A host-side Playwright session observes media requests made by that page and returns directly playable candidates. The room stores the chosen final URL and metadata once; viewers do not rerun discovery.

The resolver is intentionally generic. It does not depend on a private Miruro API, does not decrypt protected payloads, and does not attempt Cloudflare-bypass techniques. Public research shows some Miruro projects explicitly reverse-engineer encrypted/Cloudflare-protected endpoints; those techniques are intentionally outside WatchParty's provider boundary. citeturn920420search0turn920420search2

For browser playback, the external provider uses native HTML media where supported and hls.js for HLS. hls.js is an active browser HLS implementation; the current package release found during research is 1.7.1. citeturn720365search6turn738930search0

For realtime state, WebSocket is now the preferred transport with SSE/poll fallback. The `ws` server package is currently 8.21.3 and has no runtime dependencies; compression stays disabled for this small state payload to avoid needless CPU/memory overhead. citeturn600547search0turn600547search5
