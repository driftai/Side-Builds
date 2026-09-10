#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source .venv/bin/activate 2>/dev/null || true
BASE_URL="${1:-http://127.0.0.1:1919}"
echo "Probing $BASE_URL/v1/models"
curl -fsS "$BASE_URL/v1/models" | python3 -m json.tool
