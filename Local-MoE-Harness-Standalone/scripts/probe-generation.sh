#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

read -r RUNTIME_URL HARNESS_URL MODEL <<EOF
$(cd "$ROOT" && python3 - <<'PY'
from app.config import load_settings
s = load_settings()
runtime = s["runtime_base_url"].rstrip("/")
harness = f"http://127.0.0.1:{s['harness_port']}"
model = s.get("runtime_model", "")
print(runtime, harness, model)
PY
)
EOF

echo "==> FreeToken health"
curl -fsS "$RUNTIME_URL/health"
echo
echo

echo "==> FreeToken models"
curl -fsS "$RUNTIME_URL/v1/models"
echo
echo

echo "==> Direct FreeToken generation"
python3 - "$RUNTIME_URL" "$MODEL" <<'PY'
import json
import sys
import urllib.request

EXPECTED = "LOCAL_GENERATION_OK"
base, configured_model = sys.argv[1:3]
with urllib.request.urlopen(f"{base}/v1/models", timeout=10) as r:
    models = json.load(r).get("data", [])
model = (models[0].get("id") if models else "") or configured_model
if not model:
    raise SystemExit("ERROR: FreeToken did not report a model id.")
payload = json.dumps({
    "model": model,
    "messages": [{"role": "user", "content": f"Reply with exactly: {EXPECTED}"}],
    "temperature": 0,
    "max_tokens": 64,
}).encode()
req = urllib.request.Request(
    f"{base}/v1/chat/completions",
    data=payload,
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=300) as r:
    doc = json.load(r)
text = doc["choices"][0]["message"].get("content", "") or ""
reasoning = doc["choices"][0]["message"].get("reasoning_content", "") or ""
combined = f"{text}\n{reasoning}"
print(json.dumps({"model": model, "content": text, "reasoning_content": reasoning}, indent=2))
if EXPECTED not in combined:
    raise SystemExit(
        f"ERROR: FreeToken produced output, but not the expected semantic sentinel {EXPECTED!r}. "
        "Transport is alive but model generation is not correct."
    )
PY
echo

echo "==> Harness status"
curl -fsS "$HARNESS_URL/api/status"
echo
echo

echo "==> Harness generation"
python3 - "$HARNESS_URL" <<'PY'
import json
import sys
import urllib.request

EXPECTED = "HARNESS_GENERATION_OK"
base = sys.argv[1]
payload = json.dumps({
    "message": f"Reply with exactly: {EXPECTED}",
    "temperature": 0,
    "max_tokens": 64,
}).encode()
req = urllib.request.Request(
    f"{base}/api/chat",
    data=payload,
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=300) as r:
    doc = json.load(r)
message = doc["choices"][0]["message"]
text = message.get("content", "") or ""
reasoning = message.get("reasoning_content", "") or ""
combined = f"{text}\n{reasoning}"
print(json.dumps({"content": text, "reasoning_content": reasoning}, indent=2))
if EXPECTED not in combined:
    raise SystemExit(
        f"ERROR: Harness returned model output, but not the expected semantic sentinel {EXPECTED!r}. "
        "Do not mark generation healthy."
    )
PY

echo
echo "PASS: direct FreeToken generation and harness generation both produced the requested semantic sentinels."
