# Nuvio Onion Wrapper Security Model

The wrapper is intended to be a local browser wrapper around a locally built Nuvio distribution.

## Host boundary

- The HTTP server binds to `127.0.0.1` by default. It is not intended to be exposed directly to the LAN or Internet.
- Only the wrapper entry page, wrapper assets, and files under the generated `nuvio/dist` directory are served.
- Wrapper source files, configuration files, reports, scripts, and arbitrary filesystem paths are not served over HTTP.
- `safe_child()` prevents path traversal outside the generated Nuvio distribution.

## Credential boundary

- `nuvio-wrapper.properties`, local environment files, and generated `nuvio.env.js` are ignored by Git.
- Only explicitly public browser configuration is emitted into the runtime environment.
- Service secrets, API-key fields intended to remain private, passwords, and client secrets are not exported to browser JavaScript by the wrapper.
- A publishable/anonymous Nuvio client key is treated as browser-safe configuration.

## Network boundary

- The generic arbitrary remote proxy has been removed.
- The only outbound proxy exposed by the wrapper is the Stremio-compatible addon API proxy.
- Addon proxy requests require HTTPS and a supported API path (`manifest.json`, `catalog/`, `meta/`, `stream/`, or `subtitles/`).
- Literal private, loopback, link-local, reserved, and multicast addresses are rejected.
- DNS resolution is checked so hostnames resolving to private addresses are rejected.
- Redirects are revalidated against the same public-target policy.
- Browser cookies, Authorization headers, Origin, Referer, and other ambient credentials are not forwarded to addon servers.
- TLS certificate verification is never silently disabled.

## Remote exposure guidance

The wrapper is not designed to be a general-purpose public web server. Do not place the local port behind a public tunnel without first adding an explicit authenticated gateway appropriate for that deployment.

## Verification

Run `SMOKE_TESTS.bat` from the wrapper directory. It runs the existing functional smoke tests and the security regression suite in `tests/test_security.py`.

The security suite verifies private-target rejection, DNS-aware SSRF protection, addon path validation, browser credential redaction, filesystem allow-listing, removal of the generic proxy, and removal of insecure TLS fallback behavior.
