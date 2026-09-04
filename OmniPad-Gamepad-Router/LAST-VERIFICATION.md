# OmniPad Gamepad Router — Last Verification

## Current handoff

Phase 1 & Phase 2 Architecture Modularization remain complete. This handoff also records the public-session privacy/security hardening pass.

### Change scope
- **Architecture baseline:** 450-line source ceiling with explicit module ownership and architecture checker.
- **Remote Cloudflare UX:** local background-routing controls are hidden on `*.trycloudflare.com` player sessions.
- **Keyboard latency:** keydown/keyup transitions are flushed immediately in addition to the render-loop transport.
- **Mouse camera:** bounded mouse camera pad with pointer-lock support and release safety.
- **Keyboard types:** selectable physical key schemes including Standard PC, 65% Compact, Arrowless/60%, ESDF + IJKL, and WASD + HJKL Camera.
- **Security boundary:** public Cloudflare sessions are restricted to player surfaces; host dashboard, host telemetry, target management, tunnel control, background-helper APIs, and slot-management mutations are local/private-network only.
- **Remote status redaction:** public status endpoints no longer expose local IPs, executable paths, process IDs, window titles, tunnel binary paths, or the room bearer code.
- **Observer containment:** observer WebSockets are read-only and cannot submit controller input.
- **Helper source validation:** the privileged `background_keyboard_helper` source is accepted only from a local client, preventing remote source spoofing.
- **Room entropy:** omitted `--code` now generates a fresh 64-bit random room code per server run.
- **Tunnel process containment:** the launcher no longer kills every `cloudflared.exe` process on shutdown.
- **Unified control center:** managed background start, status/URLs, tunnel toggles, panic release, graceful stop, diagnostics, scoped cleanup, and guarded UMDF lifecycle controls are available from `control.bat`.
- **Contained install/repair:** `control.bat` exposes one status/repair entry point for Python, repository packages, ViGEmBus, a signed repo-local Cloudflare binary, and the bundled normal-mode UMDF keyboard. Runtime repair excludes WDK, Visual Studio, DevCon, cloudflared services, VHF installation, and boot-mode changes.
- **Normal-mode virtual keyboard:** UMDF 2 source, HID descriptor, vendor feature bridge, driver watchdog, backend discovery, package build, and dashboard integration are implemented without boot-mode changes.
- **Preserved VHF path:** the KMDF/VHF source remains maintained as a future Microsoft-signing route.
- **Input pipeline ownership:** multi-client packet fusion, key mapping, SOCD handling, and normalized state construction are isolated from `SlotManager` behind a stable facade.
- **Keyboard isolation:** physical keyboard types, fixed clickable presets, and host output selection are independent; browser-resolved keyboard state is not remapped a second time, preventing W/BACK and RS/LS cross-talk.
- **Runtime visibility and efficiency:** `control.bat` starts a visible live viewer, ordinary Uvicorn lifecycle output is not mislabeled as an error, successful status traffic is quiet, and browser polling is WebSocket/demand driven.

### Security modules & documentation
- `router/security.py`
- `tests/test_security.py`
- `tests/test_security_boundaries.py`
- `tests/test_websocket_security.py`
- `tools/scan_secrets.py`
- `SECURITY.md`
- `MODULARIZATION.md`
- `MODULARIZATION-MAP.md`

### Verification status
- **Architecture Gate:** Passed (`tools/check_architecture.py` — 0 violations across all 49 covered source files within the 450-line limit; largest file is `static/js/play.js` at 399 lines).
- **Security regression tests:** 100% passed across all 3 dedicated security test suites (Cloudflare detection, local-only HTTP endpoint matrix, target/status metadata redaction, read-only observer input injection prevention, authoritative slot handoffs, helper source spoofing rejection, and malformed frame resilience).
- **Full Git History Secret Scan:** Complete repository-history scan via `tools/scan_secrets.py` found 0 secret patterns, tokens, private keys, or credentials at the audited checkpoint.
- **Automated runtime suite:** All 23 stages passed (architecture plus 22 / 22 test suites), including direct input-fusion/normalization coverage, runtime-efficiency checks, control-center ownership/shutdown, install/repair containment, pinned package integrity, and UMDF virtual keyboard report/bridge/source contracts.
- **UMDF native build:** x64 Debug package built with UMDF 2.15; API validation and Inf2Cat passed with 0 warnings and 0 errors. The catalog was locally signed and installed without Test Mode, BCD, Secure Boot, or reboot changes.
- **Bundled UMDF runtime:** DLL, INF, catalog, and public certificate are committed as a minimal x64 package; every SHA-256 is pinned and the catalog signer thumbprint is checked before trust. SetupAPI/PnPUtil replaces the WDK-only DevCon runtime dependency. A clean `git archive` reproduced the exact signed INF hash and passed the install/repair suite. The new interop compiles and the already-installed device remained healthy; clean-machine first-install validation remains intentionally deferred because the accepted UAC run exercised the existing-device repair path.
- **Elevated existing-device repair:** The complete `RepairAll` path was accepted through UAC and passed. Windows reported the pinned package already present and current at `ROOT\HIDCLASS\0003`; the installer now recognizes PnPUtil's benign `ERROR_NO_MORE_ITEMS` (`259`) result only when the exact post-install device health check also passes.
- **UMDF installed-device smoke:** All 13 checks passed against the live device. Windows exposed a separate keyboard collection and vendor control collection; 171 device-specific Raw Input events verified make/break, modifiers, six-key rollover, duplicate suppression, heartbeat/watchdog behavior, 64 rapid transitions ending neutral, backend lifecycle, and endpoint reopen.
- **Repair/live tunnel:** Core repair passed end to end without unnecessary UAC, created a real ViGEm Xbox controller, installed an Authenticode-valid Cloudflare `2026.8.3` binary under ignored `.runtime/bin`, brought a Quick Tunnel to `active`, and then gracefully stopped the router/tunnel with no repository process left behind.
- **Cloudflare browser input:** A fresh Quick Tunnel joined from a 390x844 browser viewport with the URL room code, hid local-only routing controls, routed W to LS only and ArrowUp to RS only, and returned both to neutral. The sampled session reported 73 ms ping, 43 sent input packets, 2 coalesced drops, 13 duplicate drops, 0 backpressure drops, and 0 queued bytes; physical gameplay feel remains a user play-test item.

### Security conclusion
The public player path is intentionally a bearer-link model: possession of the current tunnel URL and room code grants room access. Host-management APIs are fully contained and separated from the public tunnel, sensitive Windows target metadata is completely redacted, and remote input channels are strictly bound to assigned slots.

### Review readiness
**Code-publication readiness: APPROVED.** The current source and entire Git history are verified 100% clean of credentials, tokens, or private secrets, with robust endpoint containment and WebSocket authorization invariants certified by automated regression tests.
