# WatchParty Standalone — Modularization Rules

## Purpose

WatchParty is intentionally maintained as a modular application. The goal is to keep individual source files small enough to understand, test, review, and safely modify without repeatedly loading unrelated context.

## Hard source-file ceiling

**450 physical lines per source file is the maximum for normal project source.**

A file approaching 400 lines is a refactoring signal, not a target. Do not compress code into unreadable one-liners or remove useful structure merely to evade the limit.

The 450-line rule applies to JavaScript/TypeScript source, Node server modules, browser/client modules, and launcher/test-harness source where practical. It excludes generated lockfiles, third-party/vendor code, reports, and other machine-generated artifacts.

Intentional exceptions must be documented here and enforced explicitly by the architecture checker.

## One responsibility per module

A module should have one clear reason to change. Examples include room domain logic, HTTP/API routing, LAN discovery, SSE transport, remote polling, YouTube parsing/player lifecycle, playback synchronization, client storage, UI wiring, launcher orchestration, and test helpers.

Do not keep adding unrelated responsibilities to an existing large file simply because the code is already there.

## Entry-point rule

`server.js` and browser bootstrap files are thin composition roots. They load configuration, wire modules, start the application, and expose the minimal integration surface. Business logic belongs in imported modules.

## Dependency direction

Prefer `entrypoint -> application/services -> domain/helpers`. Avoid circular imports and keep domain modules independent of UI, HTTP response objects, and tunnel implementation details.

## Fragment-first context

Future changes should follow `changed file -> directly imported dependencies -> directly affected tests -> small regression ring`. Do not repeatedly load the whole application when a connected fragment is sufficient. Test output follows the same philosophy: summarize first, expand on failure or dependency relevance.

## Root-cause-first debugging rule

**Do not pile symptom patches on top of each other.** When a bug survives a patch, appears intermittently, or reappears only on later lifecycle cycles, stop and identify the authoritative state transition, ownership boundary, lifecycle, race, or protocol assumption that is actually causing it. Prefer fixing that underlying invariant in the module that owns it.

For playback, explicitly model states such as `playing`, `paused`, and `ended` rather than repeatedly inferring them from player position, timers, DOM state, or UI labels. A new observer/interceptor/timer is justified only when it owns a genuinely separate responsibility; it must not exist solely to compensate for another module's incorrect state model.

**Ownership integrity:** a synchronization helper may correct drift, but it must not silently replace or monkey-patch the authoritative playback lifecycle function. Lifecycle ownership stays explicit; helpers are called through a named delegation boundary. Regression smokes must cover that boundary when terminal or cross-device states are involved.

Every rare or regression bug should produce a regression test that reproduces the underlying failure sequence. When the failure is lifecycle-dependent, the smoke should exercise repeated cycles (for example multiple end -> replay cycles) rather than only the first occurrence.

## Failure-to-invariant repair protocol

When a real device or user reproduces a bug that automation missed, treat the passing suite as **incomplete evidence**, not proof that the physical failure is an edge case.

Before adding another patch:

1. Capture the smallest real failure sequence, including device roles, lifecycle state, repeated-cycle count, and ordering of events.
2. Trace the full execution path from authoritative state -> transport -> receiving client -> final runtime owner. Check module load order, globals, wrappers, replacements, monkey-patches, duplicate listeners, and delegation boundaries. The function that looks correct in source is not sufficient evidence if another module replaces or bypasses it later.
3. Identify the broken invariant and the single module that owns that invariant. Fix the owner before adding compensating observers, timers, retries, or interceptors.
4. Upgrade the regression smoke to reproduce the **actual failure topology**. Multi-device failures require multi-context coverage; terminal/lifecycle failures require the relevant terminal state; repeated failures require multiple cycles. A permissive mock that allows behavior the real runtime rejects is not adequate coverage.
5. Only after the root fix passes the new reproducer should the broader regression ring and full suite be used as confirmation.

If a patch passes automation but fails on a real device, the next change must first improve the test model so that the prior implementation can fail for the same reason. Do not declare success until the regression test would have caught the bug that was actually observed.

Each such incident should leave behind a compact, reusable invariant: failure sequence -> authoritative owner -> root cause -> regression smoke. This turns rare bugs into permanent project knowledge instead of accumulating workaround layers.

## Refactoring protocol

When a module approaches 450 lines: identify coherent responsibilities, extract the least-coupled responsibility first, preserve behavior, add targeted smoke coverage, run the affected regression ring, run the full suite, and confirm no unrelated/generated artifacts were introduced.

## Future-feature rule

**Every new feature must choose its owning module before implementation.** Do not grow `server.js`, `public/app.js`, or another already-large file by default. A new source file is subject to the same 450-line ceiling immediately, even before staging.

## Enforcement

Run `npm run test:architecture`. The checker scans the working tree, including new/untracked source files, and fails non-zero when a normal project source file exceeds 450 lines. Architecture violations are a maintenance failure, not an informational warning.

For continuous local enforcement, run `npm run test:architecture:watch`. It performs one quiet initial check and then watches source directories, emitting no routine success messages and reporting only detected violations or checker errors. It is designed to run beside Astro/development without flooding the terminal or agent context.

## Smoke/test policy

The architecture check is part of the normal smoke/full test gates. It must remain cheap and low-noise. Detailed diagnostics belong in files/artifacts rather than routine stdout. Keep targeted regression smokes adjacent to the responsibility they protect.

## Final verification handoff

At the end of every completed engineering pass, update `LAST-VERIFICATION.md` with only the compact final state: tested SHA, local SHA, change scope, relevant smoke/test results, physical-device status, artifacts, and review readiness. This file is the canonical small handoff for review/chat context; do not require a full terminal transcript to understand the final result.

## Current modularization target

### Browser

`public/app.js` should become a thin composition root with focused modules for client/session state, storage, transport, room API, YouTube lifecycle, playback synchronization, UI, and network/share links.

### Server

`server.js` should become a thin bootstrap with focused modules for config, network discovery, room/domain state, YouTube parsing, playback, HTTP/static serving, room routes, SSE, and lifecycle cleanup.

The split must follow actual responsibilities and imports, not arbitrary line slicing.

## Quality bar

Modularization is complete only when no normal source module exceeds 450 lines, entrypoints are composition-focused, behavior remains covered by smoke/Playwright tests, integration checks remain separated from deterministic tests, `tools/cloudflared.exe` stays local-only, runtime state stays ignored, and the local checkout can match the exact verified GitHub commit.

This rule exists to keep WatchParty maintainable as it grows and prevent future feature additions from recreating the monoliths this refactor removes.
