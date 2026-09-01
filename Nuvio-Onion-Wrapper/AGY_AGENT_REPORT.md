# Nuvio Onion Wrapper — Antigravity CLI Investigation Report

## Current state

This is a local Windows browser wrapper around NuvioTVSmart.

User workspace:

```text
C:\Users\alvin\Downloads\temp\
├── nuvio\
└── Nuvio-Onion-Wrapper-v16\
```

The wrapper must load the built Nuvio browser app from:

```text
C:\Users\alvin\Downloads\temp\nuvio\dist\
```

Do **not** assume Nuvio is physically inside the wrapper. The launcher supports both `.nuvio` and `..nuvio` and `NUVIO_PATH`.

## Known-good behavior

- Nuvio source builds successfully with Node v24.13.0 / npm 11.6.2.
- `npm install` and `npm run build` completed successfully.
- Generated build includes `dist/index.html`, `dist/app.bundle.js`, `dist/core-js.bundle.js`, `dist/nuvio.env.js`.
- Wrapper runs at `http://127.0.0.1:8797/`.
- Nuvio backend discovery works and QR account login works.
- Account sync is working.
- Trailer video plays.
- Trailer must remain **user initiated**; never auto-call Play because the query string contains `autoplay=1`.
- The wrapper's former black status box was removed.

## Current bugs to reproduce

### Bug A — mouse input dies on detail pages

From the home screen, mouse selection works. After opening a movie/show detail page, mouse clicks on detail-page controls do not reliably activate Nuvio actions.

Known Nuvio source behavior:

`nuvio/js/ui/navigation/focusEngine.js`

Current upstream `FocusEngine.init()` registers pointer move/click handlers only inside:

```js
if (Platform.isWebOS()) { ... }
```

The browser adapter therefore does not get the same pointer activation path as webOS. The detail screen does expose `onPointerActivate()` for actions such as `toggleTrailer`, `openSharedTrailer`, and `openTmdbEntity`.

Current upstream references:

- `nuvio/js/ui/navigation/focusEngine.js`
- `nuvio/js/ui/screens/detail/metaDetailsScreen.js`

Relevant behavior in `metaDetailsScreen.js`:

```js
onPointerActivate(target) {
  const actionTarget = target?.closest?.("[data-action]");
  const action = String(actionTarget?.dataset?.action || "");
  ...
}
```

and detail controls are rendered as `.focusable` elements with `data-action`, for example `playDefault`, `toggleLibrary`, `toggleWatched`, etc.

v16 includes a wrapper-side pointer bridge. Test whether it actually invokes the expected detail action rather than merely changing CSS focus.

### Bug B — no streams found

Opening a title such as **Minions & Monsters** shows:

```text
All
No streams found
```

Previous browser console evidence included:

```text
GET https://94c8cb9f702d-tmdb-addon.baby-beamup.club/catalog/series/tmdb.language.json
net::ERR_FAILED 504
```

and browser CORS errors for that addon.

Important: a TMDB catalog addon is normally metadata/catalog functionality; do not assume that addon is a stream provider. Nuvio's stream repository only queries installed addons that advertise a compatible `stream` resource and then calls:

```text
/stream/{type}/{id}.json
```

Therefore the first diagnostic question is **whether the signed-in profile actually has an enabled stream-capable addon installed**. Inspect the actual addon list and manifests before changing the player.

Current installed profile previously displayed approximately:

```text
5 addons
4 plugins
2 library
3 progress
3 watched
```

This is not proof that a stream-capable addon exists.

### Bug C — YouTube console noise

Observed console messages include:

```text
Allow attribute will take precedence over 'allowfullscreen'.
```

This is harmless.

Observed YouTube telemetry failures:

```text
net::ERR_BLOCKED_BY_CLIENT
```

These are likely browser/content-blocker requests to YouTube logging/ad endpoints and are not evidence that the video media stream failed. The trailer itself currently plays.

There was also a postMessage origin mismatch involving `https://www.youtube.com` and `http://127.0.0.1:8797`; inspect whether this is only YT iframe API messaging noise or actually breaks controls.

## How to start the wrapper

Open CMD or PowerShell:

```bat
cd /d C:\Users\alvin\Downloads\temp\Nuvio-Onion-Wrapper-v16
START_WRAPPER.bat
```

Expected console:

```text
Nuvio Wrapper running at http://127.0.0.1:8797/
Nuvio root: C:\Users\alvin\Downloads\temp\nuvio
Inner app: C:\Users\alvin\Downloads\temp\nuvio\dist\index.html
QR config: READY via discovery
```

## Automated smoke test

With the server running, open another CMD:

```bat
cd /d C:\Users\alvin\Downloads\temp\Nuvio-Onion-Wrapper-v16
SMOKE_TESTS.bat
```

Or directly:

```bat
py -3 smoke_tests.py
```

The smoke tests verify:

- Nuvio root discovery
- required `dist` artifacts
- wrapper HTTP root
- wrapper JS
- `/__wrapper__/nuvio-entry`
- `/__wrapper__/diagnostics`

These are intentionally network-safe sanity checks, not a substitute for browser interaction testing.

## Browser smoke test

Open `http://127.0.0.1:8797/` in Edge/Chrome.

Press F12 → Console. Paste `BROWSER_SMOKE_TESTS.js` from the wrapper directory, or paste its contents directly.

Use it after selecting a movie and again after opening its detail page. Compare:

```text
active
focused
pointerAtCenter
detailFocusables
trailers
```

Then manually click these controls:

1. Play
2. Library
3. Watched
4. Trailer
5. Creator/cast tab
6. Any season/episode button for a series

Record which exact `data-action` stops responding.

## Stream investigation steps

In DevTools → Network, enable Preserve log.

Then:

1. Open a known movie.
2. Go to its stream/source selection.
3. Filter requests by `stream`.
4. Record every request matching:

```text
*/stream/*
```

5. For each request, record HTTP status and response JSON.
6. Inspect the installed addon manifests. Confirm at least one enabled addon declares a `stream` resource compatible with `movie` or `series`.
7. If there is no stream-capable addon, the correct fix is addon setup, not a player/wrapper fix.
8. If a stream-capable addon exists but its `/stream/...` request gets CORS/403/404/5xx, record the addon base URL, status, and response body.
9. Test the same addon URL directly in a new tab or with a command-line request from the same PC.

Useful console query after login:

```js
performance.getEntriesByType('resource')
  .filter(x => /\/stream\//i.test(x.name))
  .map(x => x.name)
```

Also inspect the actual current addon records through the Nuvio UI: Settings → Integrations/Addons, and capture the enabled addon names and URLs (redact any account/token data).

## What not to do

- Do not inject a fake account credential or bypass Nuvio authentication.
- Do not use a Supabase service-role key in the browser.
- Do not disable browser security globally.
- Do not auto-click Play or auto-start trailers.
- Do not assume every addon is a stream addon.
- Do not replace Nuvio's media URLs with arbitrary external URLs.

## Relevant upstream source references

Repository:

```text
https://github.com/NuvioMedia/NuvioTVSmart
```

Current upstream build instructions are `npm install` and `npm run build`.

Relevant source files:

```text
nuvio/js/ui/navigation/focusEngine.js
nuvio/js/ui/screens/detail/metaDetailsScreen.js
nuvio/js/data/repository/streamRepository.js
nuvio/js/data/repository/addonRepository.js
nuvio/local.example.properties
nuvio/docs/youtube-proxy.html
```

Nuvio's current contribution policy says browser-development-mode/platform-specific behavior changes should be treated as documented bug fixes with manual testing notes. See `CONTRIBUTING.md`.
