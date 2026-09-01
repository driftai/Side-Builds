# WatchParty Standalone Smoke Test Scaffolding

This directory is the core verification scaffold for WatchParty Standalone.

The smoke system is intentionally **low-noise and change-aware**: show a compact result first, then expose detail only for failures or tests connected to changed code.

## Layers

- `node/` — deterministic HTTP/server smoke tests. Discover and assert against routes actually implemented by the server modules; never invent health endpoints.
- `browser/` — Playwright end-to-end tests for the real UI, with host/viewer browser contexts.
- `integration/` — environment-dependent checks for LAN, sslip.io, Cloudflare, and live YouTube.
- `fixtures/` — reusable test data and deterministic fixtures.
- `helpers/` — reusable test helpers; keep protocol-specific assertions close to their layer.

## Low-noise / change-aware rules

1. **Summary first.** A passing run should print only a compact summary such as `WATCHPARTY SMOKE: PASS 18 | FAIL 0 | SKIP 3 | CHANGED 2 | SCOPE playback,reconnect`.
2. **No success spam.** Do not print request bodies, full responses, browser console output, DOM dumps, stack traces, or unchanged-file contents for passing tests.
3. **Failures expand.** On failure, print the failed test ID, relevant assertion, small bounded context, and artifact path. Full traces/screenshots/HTML reports stay on disk.
4. **Changed scope first.** Determine changed files from Git before selecting tests. Prefer tests directly connected to changed files, then a small dependency/regression ring.
5. **Dependency-aware expansion.** Shared/core changes expand to connected suites; docs-only or unrelated changes should not automatically run every integration test.
6. **Full suite is opt-in.** Provide an explicit full verification command. The normal developer smoke should stay fast and quiet.
7. **No giant diffs.** Report changed paths and compact diff/stat information first. Inspect exact hunks only when a failure or dependency requires them.
8. **Machine-readable detail stays in artifacts.** JSON/JUnit/Playwright reports may contain complete results while stdout remains concise.
9. **No secrets in diagnostics.** Never print cookies, tokens, authorization headers, secrets, or full environment dumps.
10. **Stable test IDs/tags.** Tests should have short stable IDs/categories so changed-file scope can select relevant tests without parsing huge output.

## Architecture gate

The project has a hard **450 physical-line maximum for normal source modules**. The architecture check is intentionally low-noise and should be treated as a gate:

`npm run test:architecture`

It reports only source files that violate the ceiling and exits non-zero when violations exist.

The line limit is a maintainability boundary, not an invitation to compress code into unreadable one-liners. When a file approaches the ceiling, extract a coherent responsibility into a focused module instead of squeezing more behavior into the file.

See `MODULARIZATION.md` for the dependency/layer rules and the current refactor targets.

## Suggested execution model

### Fast/default

Run the architecture gate, deterministic Node smokes, and the smallest relevant Playwright regression set based on changed files.

Normal output should be one summary line. If failures occur, print only the failed IDs and artifact locations, then use the detailed report on disk for diagnosis.

### Review/full

Run architecture + all deterministic Node and Playwright tests, followed by explicitly available LAN/sslip.io/Cloudflare/YouTube integrations. Keep stdout concise and write detailed reports to ignored artifact directories.

### Live YouTube integration

Live YouTube is an **explicit integration check**, not part of the offline/default smoke gate. It must exercise the real WatchParty YouTube IFrame path rather than only an oEmbed/HTTP reachability probe.

Run it with:

`npm run test:youtube-live`

The live test verifies the real IFrame API initializes, WatchParty reports the source as ready, and a YouTube embed for the requested video is actually attached. It also supports an explicit `LIVE_YOUTUBE_URL` override for testing arbitrary real-world YouTube URLs.

A live YouTube failure should be reported as an integration failure with bounded diagnostics, while a missing Internet/browser prerequisite should be reported as `SKIP` rather than making the deterministic baseline fail.

## Local checkout synchronization / definition of done

GitHub `main` is the canonical WatchParty source. Astro uses the local Windows checkout only as the executable verification environment.

Local checkout:

`C:\Users\alvin\Downloads\Private-Test-Builds\watchparty-standalone`

After completing a code or test-harness change:

1. Verify the intended change.
2. Push the verified commit to GitHub.
3. Record the exact tested GitHub SHA.
4. Synchronize the local checkout to that exact `origin/main` SHA with a fast-forward pull.
5. Confirm `git status --short` is clean except for intentionally ignored machine-local dependencies such as `tools\cloudflared.exe`.
6. Confirm the local checkout SHA exactly matches the tested GitHub SHA.
7. Never reset/delete machine-local files merely to make synchronization easier; explain a blocking condition instead.

Astro's final report must include both the remote tested SHA and the local checkout SHA and state whether they match.

## Change-to-test mapping

Astro should maintain a lightweight mapping from source areas to test tags/suites. Starting points after modularization:

- `server.js` / server composition modules → `server`, `rooms`, `sync`, `sse`, `reconnect`, `lan`
- `public/app.js` / browser composition modules → `ui`, `playback`, `sync`, `reconnect`, `chat`, `browser`, `youtube`
- player modules → `youtube`, `playback`, `sync`, `browser`
- transport modules → `sse`, `polling`, `reconnect`, `remote`, `lan`
- network modules → `lan`, `sslip`
- `scripts/*` → `launcher`, `lan`, `remote`
- `tools/*` → `remote`, `cloudflared`
- `package.json` / Playwright config / smoke runner → `test-harness`, `browser`

This mapping is a starting point, not a reason to run unrelated tests. Refine it from actual imports, routes, and behavior.

## Playwright output policy

Use Playwright's concise `dot` or `line` reporter for routine runs. Keep JSON/HTML/trace artifacts for deeper inspection. Playwright supports concise reporters plus separate JSON/HTML reporting, which fits this model. urlPlaywright reporters documentationhttps://playwright.dev/docs/test-reporters

Failure artifacts belong in ignored local directories such as `test-results/` and `playwright-report/`; never commit them. Playwright also supports separate HTML reports and trace inspection for failures. urlPlaywright CI/reporting documentationhttps://playwright.dev/docs/ci-intro

## Rules

1. Tests must exercise the real WatchParty implementation.
2. Deterministic smoke tests must not require Internet access.
3. Live YouTube, LAN, sslip.io, and Cloudflare checks must be explicitly marked/skipped when unavailable.
4. `tools/cloudflared.exe` remains a local dependency and must not be committed.
5. Do not create fake API endpoints solely to satisfy tests.
6. Browser tests should collect screenshots/traces on failures, not dump them into stdout.
7. Keep regression coverage for room lifecycle, synchronization, reconnect behavior, and the old forced-seek problem.
8. Prefer small composable tests over one enormous end-to-end smoke.
9. A normal pass should be quiet; a failure should become progressively more detailed only as needed.
10. Live YouTube tests must exercise the actual embedded player path, not merely an external HTTP endpoint.
11. Architecture violations are maintenance failures, not informational warnings.
12. New features must enter through a focused module and must not grow an already-large monolith by default.
13. Modularization must preserve behavior; refactors are accepted only after the relevant regression ring and full suite pass.

Astro should fill in and run the modularized architecture against the current implementation before adding assertions for routes or behaviors that have not been verified.