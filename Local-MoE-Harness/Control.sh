#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL="$ROOT/scripts/control.sh"
CHAT_URL="http://localhost:5180"

open_chat() {
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Start-Process '$CHAT_URL'" >/dev/null 2>&1 || true
  elif command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "" "$CHAT_URL" >/dev/null 2>&1 || true
  else
    echo "Open $CHAT_URL in your browser."
  fi
}

if (( $# > 0 )); then
  exec "$CONTROL" "$@"
fi

while true; do
  clear || true
  cat <<'EOF'
=====================================================
               LOCAL MOE HARNESS
=====================================================

 [1] Start Everything + Open Chat
 [2] Show Status
 [3] Open Chat
 [4] Stop Everything
 [5] Show Log Paths
 [6] Exit
EOF
  echo
  read -r -p "Select an option: " choice
  case "$choice" in
    1)
      if "$CONTROL" start; then
        open_chat
      fi
      echo
      read -r -p "Press Enter to continue..." _
      ;;
    2)
      "$CONTROL" status
      echo
      read -r -p "Press Enter to continue..." _
      ;;
    3)
      open_chat
      ;;
    4)
      "$CONTROL" stop
      echo
      read -r -p "Press Enter to continue..." _
      ;;
    5)
      echo "Harness log:   $ROOT/logs/harness-server.log"
      echo "FreeToken log: $ROOT/logs/freetoken-server.log"
      echo
      read -r -p "Press Enter to continue..." _
      ;;
    6)
      exit 0
      ;;
    *)
      echo "Invalid option."
      sleep 1
      ;;
  esac
done
