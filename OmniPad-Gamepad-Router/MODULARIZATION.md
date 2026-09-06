# OmniPad Gamepad Router — Modularization Rules

## Purpose

OmniPad is maintained as a modular input-routing application. Individual source files should remain small enough to understand, test, review, and safely modify without loading unrelated controller, transport, targeting, or UI logic.

## Hard source-file ceiling

**450 physical lines per normal project source file is the maximum.**

A file approaching 400 lines is a refactoring signal, not a target. Do not compress code or remove readability merely to evade the limit.

The rule applies to Python application and test modules, browser JavaScript/TypeScript, CSS/HTML, native C/C++/C# driver source, PowerShell, shell, and batch launchers. Generated artifacts, packaged binaries, build output, lockfiles, third-party/vendor code, reports, and documentation are excluded explicitly in `MODULARIZATION-EXCEPTIONS.json`.

Existing oversized legacy modules are explicitly tracked in `MODULARIZATION-MAP.md`. The architecture checker rejects every new or unapproved overage.

## One responsibility per module

A module should have one clear reason to change. Examples include controller state, output backends, slot ownership, WebSocket transport, target discovery, tunnel lifecycle, keyboard HID packing, touchscreen layout state, and UI composition.

Do not keep adding unrelated responsibilities to a large file because the code is already there.

## Entry-point rule

`server.py` is a composition root: application setup, route registration, dependency wiring, and lifecycle startup belong there. Route handlers, WebSocket protocol details, serialization, and domain behavior should move into focused modules.

Browser entrypoints should similarly coordinate focused modules rather than becoming feature buckets.

## Dependency direction

Prefer:

`entrypoint -> application/services -> domain/helpers -> platform adapters`

Avoid circular imports. Domain/state modules should not depend on HTML or UI objects.

## Fragment-first context

Future changes should follow:

`changed file -> directly imported dependencies -> directly affected tests -> small regression ring`

Do not repeatedly load the whole application when a connected fragment is sufficient.

## Root-cause-first debugging

Do not pile symptom patches on top of each other. When a bug survives a patch or appears after lifecycle changes, identify the authoritative state transition, ownership boundary, race, or protocol assumption that owns the failure.

Every reproduced regression should leave behind a regression test for the actual failure sequence.

## Failure-to-invariant repair protocol

When a real device reproduces a bug that automation missed:

1. Capture the smallest real failure sequence and device roles.
2. Trace authoritative state -> transport -> receiver -> runtime owner.
3. Identify the broken invariant and fix the owning module.
4. Upgrade the regression test so the previous implementation can fail for the same reason.
5. Run the targeted ring, then the broader suite.

A passing suite is incomplete evidence if it cannot model the real failure.

## Refactoring protocol

When a module approaches 450 lines:

1. Identify coherent responsibilities.
2. Extract the least-coupled responsibility first.
3. Preserve public behavior and import boundaries.
4. Add focused regression coverage.
5. Run the affected regression ring and architecture check.
6. Update `MODULARIZATION-MAP.md`.

## Future-feature rule

Every new feature must choose its owning module before implementation. Do not grow `server.py`, `router/controller.py`, or another large module by default.

## Enforcement

Run:

`python tools/check_architecture.py`

The checker scans the working tree and fails non-zero when a covered source file exceeds 450 lines without an explicit temporary entry in `MODULARIZATION-EXCEPTIONS.json`. It also rejects stale exceptions and exception entries missing an owner, reason, or removal target.

Successful runs emit one stable summary line. Full machine-readable results are written to the ignored `test-results/architecture.json` artifact.

Exceptions are migration debt, not permanent architecture. Each exception requires an owner/scope note and removal target in `MODULARIZATION-MAP.md`.

## Smoke/test policy

Architecture validation is the first full-smoke stage. `tools/run_smoke_tests.bat` emits one passing summary line by default and stores complete ignored diagnostics in `test-results/smoke.json`; use `--verbose` only when detailed passing output is needed.

## Final verification handoff

At the end of an engineering pass, update `LAST-VERIFICATION.md` with the tested SHA, change scope, relevant test results, device status, and review readiness. It is the compact handoff document for future work.
