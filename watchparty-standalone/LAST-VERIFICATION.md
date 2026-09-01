# WatchParty Standalone — Last Verification

> Astro updates this file only after running the exact current branch HEAD. This file is never copied from an older branch.

## Build identity

- Repository: `driftai/Private-Test-Builds`
- Branch: `main`
- Exact Commit SHA: `512f8a2e474cb3eb63b90af82227b891d0288e35`
- Base Integration Commit: `512f8a2` (Merge PR #3: Media engine and external provider support)
- Status: **CERTIFIED PASS**
- Automated certification: **PASSED (Astro full exact-HEAD run)**

## Current change scope

- General provider-neutral media engine beside YouTube
- Host-authorized server-side Playwright page inspection
- Direct HLS/media source support with native `<video>` and pinned local HLS.js runtime
- Bounded fatal HLS network and media error auto-recovery
- Separated browser HLS certification fixture (standard CORS-compatible Mux stream) from external CDN compatibility checks
- WebSocket preferred realtime transport with SSE/poll fallback
- Monotonic authoritative room revisions (`revision` integer rejection guard)
- Server-clock sampling for latency-aware playback projection
- Resolver public-network boundary and browser subrequest SSRF filtering
- Cross-client stale-snapshot regression coverage
- Complete multi-cycle terminal replay lifecycle state machines for both YouTube and external media

## Test Verification Suite Summary

| Gate / Suite | Command | Result | Notes |
|---|---|---|---|
| Architecture Gate | `npm run test:architecture` | **PASS** | 0 violations, max 450 lines |
| Node Smoke Suite | `node tests/smoke/run.js --node` | **PASS (32/32)** | server (15), playback-state (1), media (11), media-resolver (1), realtime (4) |
| Browser Smoke Suite | `npm run test:browser` | **PASS (25/25, 3 skipped)** | 25 deterministic browser specs passed |
| Browser HLS Fixture Gate | `npm run test:browser:hls` | **PASS (1/1)** | Mux HLS stream verified playing and progressing (4.4s) |
| Unified Smoke Gate | `npm run test:smoke` | **PASS (46/46)** | Node + Architecture + Browser suites |
| Live YouTube Smoke | `npm run test:youtube-live` | **PASS (1/1)** | 2.5s execution |
| Live Watch-Page Resolver Smoke | `npm run test:media-page-live` | **PASS (1/1)** | Miruro watch page discovered 5 streams + 3 subs (24.4s) |
| Integration Suite | `npm run test:integration` | **PASS (4/4, 1 skipped)** | LAN, CF, and YT integration tests |
| Full Test Gate | `npm test` | **PASS (50/50, 1 skipped)** | Complete test matrix green |

## Miruro Live Watch-Page Resolution Analysis

- **Target URL**: `https://www.miruro.ru/watch/171627/chainsaw-man-reze-hen?ep=1`
- **Page Load**: Loaded with HTTP 200 (`domcontentloaded` in 1.8s, title: `Watch Chainsaw Man – The Movie: Reze Arc · Miruro`)
- **Cloudflare / Bot-Evasion**: Clean load, no Cloudflare challenge widget or captcha encountered.
- **Media Requests Observed**: 5 playable `.m3u8` master and variant manifest requests intercepted.
- **Candidates Discovered**: 5 HLS stream variants discovered on CDN server `s1.watami.win`.
- **Server/Provider Labels**: Server identified as `s1.watami.win`.
- **Audio Classification**: Classified as `dub`.
- **Subtitle Tracks Discovered**: 3 English subtitle tracks (`sub.vtt`) captured from `s1.watami.win`.
- **Player Usability**: Stream manifests are standard HLS VOD playlists with 10s target duration segments. Usable by the WatchParty media player without requiring third-party browser plugins.

## Review status

- Ready for Drift review: **YES**
- Ready for merge: **HOLD (Active continuation development line)**
