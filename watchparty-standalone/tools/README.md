# WatchParty local tools

This directory is the expected local location for WatchParty's machine-installed tools.

## Cloudflared

Remote mode requires Cloudflare's `cloudflared` executable. It is intentionally **not bundled with the repository**.

For Windows:

1. Download the current Windows `cloudflared` executable from Cloudflare's official Tunnel downloads page:
   https://developers.cloudflare.com/tunnel/downloads/
2. Rename it to `cloudflared.exe` if needed.
3. Place it in this directory:
   `watchparty-standalone\tools\cloudflared.exe`
4. Verify it with:
   `.\cloudflared.exe --version`

WatchParty Remote mode checks this exact path and does not download or install Cloudflared automatically.

The executable is ignored by Git so each machine can keep its own local copy.
