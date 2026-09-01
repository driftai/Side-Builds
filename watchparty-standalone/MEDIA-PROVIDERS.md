# WatchParty Standalone — Media Providers

WatchParty now treats YouTube as one playback provider rather than the entire media model.

## Provider contract

A provider resolves an input into a room `source` object. The room distributes the resolved playable source, not the provider's private scraping/session details.

External media uses:

- `kind`: `media`
- `type`: `hls` or `file`
- `url`: final playable URL
- `originalUrl`: page URL or user-entered source
- `title`: best available title
- `server`: optional provider/server label
- `audio`: `sub`, `dub`, or null
- `subtitles`: public VTT/SRT track URLs when observed

YouTube continues to use its existing IFrame player and video ID.

## Host-only discovery

A watch page is inspected on the host machine with Playwright. The resolver observes the page's own public network/media requests and native media elements, then returns candidate HLS/media URLs and metadata. Only the selected playable source is written into room state and shared with viewers.

This means viewers do not need Playwright, do not repeat page scraping, and do not receive the host's resolver session. The final media URL is the synchronization target.

## Miruro-like watch pages

The resolver is intentionally generic rather than hard-coded to one website. A page such as a Miruro watch URL can work when its browser session exposes a directly playable media request to the page, including `.m3u8` manifests or media files. Current public research shows Miruro-derived projects commonly expose provider labels, sub/dub episode variants, M3U8 streams, subtitles, and skip timestamps, but some projects also describe reverse-engineering encrypted/Cloudflare-protected endpoints. WatchParty does not implement those bypass/decryption techniques; it only observes the browser-visible media requests from the supplied page.

## Browser playback

External HLS playback uses native browser HLS support when available and hls.js otherwise. Media playback is provider-neutral and uses the same authoritative room timeline used by YouTube.

## Synchronization

The existing room state remains the single source of truth. Viewers locally project the authoritative timeline and apply drift correction. The WebSocket transport is the preferred low-latency state transport; SSE and short polling remain fallbacks.

## Security boundary

Resolver input is intended for public HTTP(S) pages. The server must reject loopback/private destinations before host-side page inspection to avoid turning the resolver into a server-side request forgery primitive. Do not add Cloudflare bypass, Web Crypto decryption, credential harvesting, or DRM circumvention as a provider implementation.

## Testing

Provider changes require:

- deterministic media URL classification smoke
- host-only media-room authorization smoke
- Playwright UI smoke for source discovery/result selection
- viewer playback smoke for direct HLS/media state
- opt-in live external media smoke with `LIVE_MEDIA_URL`
- realtime transport smoke
- the existing full WatchParty regression suite

Do not make a live provider the default deterministic test fixture. Live provider checks must remain opt-in and must not make the normal smoke suite depend on third-party site availability.
