# Security

Local MoE Harness binds to localhost by default.

Do not expose port 5180 or the FreeToken runtime port 1919 to untrusted networks without adding an explicit authentication and network-security layer.

Model downloads are restricted to the trusted registry and immutable revisions where downloads are supported. Native-Windows engine/bootstrap downloads are pinned by SHA-256 in `config/windows-runtime.json`.

Control scripts must stop only processes proven to belong to this project root. They must not terminate unrelated applications to recover GPU resources or ports.

Report security-sensitive issues privately to the project maintainer rather than posting credentials, tokens, or private model URLs in a public issue.
