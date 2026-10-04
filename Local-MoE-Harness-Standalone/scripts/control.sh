#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT/state"
LOG_DIR="$ROOT/logs"
HARNESS_PID="$STATE_DIR/harness.pid"
FREETOKEN_PID="$STATE_DIR/freetoken.pid"
HARNESS_URL="http://127.0.0.1:5180"

mkdir -p "$STATE_DIR" "$LOG_DIR"

configure_context_profile() {
  local profile="${1:-balanced12k}"
  case "$profile" in
    balanced12k)
      export LOCAL_MOE_CONTEXT_PROFILE="balanced12k"
      : "${LOCAL_MOE_KV_RESERVE_TOKENS:=12288}"
      : "${LOCAL_MOE_MAX_PREFILL_LENGTH:=2048}"
      : "${LOCAL_MOE_PREFILL_HIT_D2D:=1}"
      : "${LOCAL_MOE_CONTEXT_GATE_TOKENS:=10800}"
      : "${LOCAL_MOE_CONTEXT_GATE_TIMEOUT:=300}"
      : "${LOCAL_MOE_NORMAL_MOE_SLOTS:=569}"
      export LOCAL_MOE_KV_RESERVE_TOKENS LOCAL_MOE_MAX_PREFILL_LENGTH LOCAL_MOE_PREFILL_HIT_D2D
      export LOCAL_MOE_CONTEXT_GATE_TOKENS LOCAL_MOE_CONTEXT_GATE_TIMEOUT LOCAL_MOE_NORMAL_MOE_SLOTS
      ;;
    fast8k)
      export LOCAL_MOE_CONTEXT_PROFILE="fast8k"
      : "${LOCAL_MOE_KV_RESERVE_TOKENS:=8192}"
      : "${LOCAL_MOE_MAX_PREFILL_LENGTH:=2048}"
      : "${LOCAL_MOE_PREFILL_HIT_D2D:=1}"
      : "${LOCAL_MOE_CONTEXT_GATE_TOKENS:=6800}"
      : "${LOCAL_MOE_CONTEXT_GATE_TIMEOUT:=120}"
      : "${LOCAL_MOE_NORMAL_MOE_SLOTS:=736}"
      export LOCAL_MOE_KV_RESERVE_TOKENS LOCAL_MOE_MAX_PREFILL_LENGTH LOCAL_MOE_PREFILL_HIT_D2D
      export LOCAL_MOE_CONTEXT_GATE_TOKENS LOCAL_MOE_CONTEXT_GATE_TIMEOUT LOCAL_MOE_NORMAL_MOE_SLOTS
      ;;
    balanced4k)
      export LOCAL_MOE_CONTEXT_PROFILE="balanced4k"
      : "${LOCAL_MOE_KV_RESERVE_TOKENS:=4096}"
      : "${LOCAL_MOE_MAX_PREFILL_LENGTH:=4096}"
      : "${LOCAL_MOE_PREFILL_HIT_D2D:=0}"
      : "${LOCAL_MOE_NORMAL_MOE_SLOTS:=783}"
      export LOCAL_MOE_KV_RESERVE_TOKENS LOCAL_MOE_MAX_PREFILL_LENGTH LOCAL_MOE_PREFILL_HIT_D2D LOCAL_MOE_NORMAL_MOE_SLOTS
      ;;
    *)
      echo "[Control] ERROR: unknown context profile '$profile' (use balanced12k, fast8k, or balanced4k)."
      return 2
      ;;
  esac
}

configure_recovery_profile() {
  export LOCAL_MOE_CONTEXT_PROFILE="recovery4k"
  export LOCAL_MOE_KV_RESERVE_TOKENS="${LOCAL_MOE_RECOVERY_KV_RESERVE_TOKENS:-4096}"
  export LOCAL_MOE_MAX_PREFILL_LENGTH="${LOCAL_MOE_RECOVERY_MAX_PREFILL_LENGTH:-1024}"
  export LOCAL_MOE_PREFILL_HIT_D2D="${LOCAL_MOE_RECOVERY_PREFILL_HIT_D2D:-0}"
  export LOCAL_MOE_NORMAL_MOE_SLOTS="${LOCAL_MOE_RECOVERY_NORMAL_MOE_SLOTS:-736}"
  export LOCAL_MOE_RECOVERY=1
}

pid_alive() {
  local pid="${1:-}"
  [[ "$pid" =~ ^[0-9]+$ ]] && (( pid > 1 )) && kill -0 "$pid" 2>/dev/null
}

read_pid() {
  local path="$1"
  [[ -f "$path" ]] && tr -d '[:space:]' < "$path" || true
}

http_ready() {
  curl -fsS --max-time 2 "$HARNESS_URL/api/status" >/dev/null 2>&1
}

harness_waiting_for_model() {
  python3 - "$HARNESS_URL" <<'PY'
import json
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1] + "/api/status", timeout=5) as response:
        status = json.load(response)
except Exception:
    raise SystemExit(1)

lifecycle = status.get("runtime_lifecycle") or {}
raise SystemExit(0 if lifecycle.get("startup_stage") == "waiting_for_model" else 1)
PY
}

sync_profile_from_harness() {
  local key value
  while IFS='=' read -r key value; do
    case "$key" in
      LOCAL_MOE_CONTEXT_PROFILE|LOCAL_MOE_KV_RESERVE_TOKENS|LOCAL_MOE_MAX_PREFILL_LENGTH|LOCAL_MOE_PREFILL_HIT_D2D)
        printf -v "$key" '%s' "$value"
        export "$key"
        ;;
    esac
  done < <(python3 - "$HARNESS_URL" <<'PY'
import json
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1] + "/api/status", timeout=5) as response:
    settings = json.load(response).get("settings") or {}

values = {
    "LOCAL_MOE_CONTEXT_PROFILE": settings.get("active_profile") or "unknown",
    "LOCAL_MOE_KV_RESERVE_TOKENS": settings.get("conversation_kv_floor_tokens"),
    "LOCAL_MOE_MAX_PREFILL_LENGTH": settings.get("max_prefill_length"),
    "LOCAL_MOE_PREFILL_HIT_D2D": settings.get("prefill_hit_d2d"),
}
for key, value in values.items():
    if value is not None:
        print(f"{key}={value}")
PY
  )
}

sync_context_gate_from_active_profile() {
  local kv="${LOCAL_MOE_KV_RESERVE_TOKENS:-4096}"
  if [[ ! "$kv" =~ ^[1-9][0-9]*$ ]]; then
    return 0
  fi

  case "$kv" in
    12288)
      export LOCAL_MOE_CONTEXT_GATE_TOKENS="${LOCAL_MOE_BALANCED_CONTEXT_GATE_TOKENS:-10800}"
      export LOCAL_MOE_CONTEXT_GATE_TIMEOUT="${LOCAL_MOE_BALANCED_CONTEXT_GATE_TIMEOUT:-300}"
      ;;
    8192)
      export LOCAL_MOE_CONTEXT_GATE_TOKENS="${LOCAL_MOE_FAST_CONTEXT_GATE_TOKENS:-6800}"
      export LOCAL_MOE_CONTEXT_GATE_TIMEOUT="${LOCAL_MOE_FAST_CONTEXT_GATE_TIMEOUT:-120}"
      ;;
    *)
      if (( kv >= 6144 )); then
        export LOCAL_MOE_CONTEXT_GATE_TOKENS="$((kv - 1392))"
        export LOCAL_MOE_CONTEXT_GATE_TIMEOUT="${LOCAL_MOE_CONTEXT_GATE_TIMEOUT:-120}"
      fi
      ;;
  esac
}

gpu_busy_preflight() {
  python3 - <<'PY'
import subprocess
import sys
import time

commands = [
    [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "nvidia-smi.exe --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits",
    ],
    [
        "nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ],
]

samples = []
for _ in range(3):
    sample = None
    for cmd in commands:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=4, check=False)
            if proc.returncode != 0:
                continue
            line = next((x.strip() for x in proc.stdout.splitlines() if x.strip()), "")
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 3:
                sample = (float(parts[0]), float(parts[1]), float(parts[2]))
                break
        except Exception:
            continue
    if sample is not None:
        samples.append(sample)
    time.sleep(0.4)

if not samples:
    raise SystemExit(1)
avg_util = sum(s[0] for s in samples) / len(samples)
latest_memory = samples[-1][1]
raise SystemExit(0 if avg_util >= 30.0 or latest_memory >= 1000.0 else 1)
PY
}

startup_profile_name() {
  if [[ "${LOCAL_MOE_RECOVERY:-0}" == "1" ]]; then
    echo "recovery"
    return 0
  fi

  case "${LOCAL_MOE_CONTEXT_PROFILE:-balanced12k}" in
    fast8k|busy)
      echo "busy"
      ;;
    balanced4k|recovery4k|recovery)
      echo "recovery"
      ;;
    *)
      echo "normal"
      ;;
  esac
}

registry_startup_budget() {
  local profile raw_timeout budget
  profile="$(startup_profile_name)"
  raw_timeout="$($ROOT/.venv/bin/python "$ROOT/scripts/model-selection.py" startup-timeout --profile "$profile" 2>/dev/null || true)"

  # Fall back conservatively if registry inspection is unavailable. The selected
  # model's profile remains authoritative whenever it can be read.
  if [[ ! "$raw_timeout" =~ ^[1-9][0-9]*$ ]]; then
    echo "180"
    return 0
  fi

  budget=$((raw_timeout + 15))
  if (( budget < 180 )); then
    budget=180
  fi
  echo "$budget"
}

start_harness() {
  if http_ready; then
    echo "[Control] Harness is already online."
    return 0
  fi

  local old_pid harness_pid runtime_pid
  local default_timeout start_timeout
  local started_at final_deadline progress_deadline
  local progress_announced=0

  default_timeout="$(registry_startup_budget)"
  if [[ "${LOCAL_MOE_RECOVERY:-0}" == "1" ]]; then
    start_timeout="${LOCAL_MOE_RECOVERY_HARNESS_START_TIMEOUT:-$default_timeout}"
  else
    start_timeout="${LOCAL_MOE_HARNESS_START_TIMEOUT:-$default_timeout}"
  fi

  if [[ ! "$start_timeout" =~ ^[1-9][0-9]*$ ]]; then
    echo "[Control] ERROR: harness startup timeout must be a positive integer."
    return 2
  fi

  old_pid="$(read_pid "$HARNESS_PID")"
  if pid_alive "$old_pid"; then
    echo "[Control] Harness process $old_pid is starting; waiting for HTTP..."
  else
    rm -f "$HARNESS_PID"
    echo "[Control] Starting Local MoE Harness..."
    nohup setsid "$ROOT/scripts/run-harness.sh" \
      >>"$LOG_DIR/harness-server.log" 2>&1 </dev/null &
    local pid=$!
    printf '%s\n' "$pid" > "$HARNESS_PID"
    echo "[Control] Harness PID: $pid"
  fi

  harness_pid="$(read_pid "$HARNESS_PID")"
  started_at=$SECONDS
  final_deadline=$((started_at + start_timeout))
  progress_deadline=$((started_at + 60))
  if [[ "${LOCAL_MOE_RECOVERY:-0}" == "1" ]]; then
    echo "[Control] Recovery harness process started (PID $harness_pid)."
  fi

  while (( SECONDS < final_deadline )); do
    if http_ready; then
      echo "[Control] Harness HTTP is online."
      return 0
    fi

    if ! pid_alive "$harness_pid"; then
      echo "[Control] ERROR: Harness process $harness_pid exited before HTTP became reachable."
      echo "[Control] Last harness log lines:"
      tail -n 30 "$LOG_DIR/harness-server.log" 2>/dev/null || true
      return 1
    fi

    if (( progress_announced == 0 )) && (( SECONDS >= progress_deadline )); then
      runtime_pid="$(read_pid "$FREETOKEN_PID")"
      if pid_alive "$runtime_pid"; then
        echo "[Control] FreeToken process $runtime_pid is still initializing while FastAPI startup is in progress."
      else
        echo "[Control] Harness startup is still preparing the selected FreeToken model."
      fi
      echo "[Control] Waiting within the selected model/profile startup budget (${start_timeout}s total)..."
      progress_announced=1
    fi

    sleep 0.5
  done

  if [[ "${LOCAL_MOE_RECOVERY:-0}" == "1" ]]; then
    echo "[Control] ERROR: Recovery harness did not become reachable within ${start_timeout}s."
  else
    echo "[Control] ERROR: Harness did not become reachable within ${start_timeout}s."
  fi
  echo "[Control] Last harness log lines:"
  tail -n 30 "$LOG_DIR/harness-server.log" 2>/dev/null || true
  return 1
}

stop_pidfile() {
  local path="$1"
  local name="$2"
  local pid
  pid="$(read_pid "$path")"

  if ! pid_alive "$pid"; then
    rm -f "$path"
    echo "[Control] $name is not running under this launcher."
    return 0
  fi

  echo "[Control] Stopping $name (PID $pid)..."
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true

  for _ in $(seq 1 40); do
    if ! pid_alive "$pid"; then
      rm -f "$path"
      echo "[Control] $name stopped."
      return 0
    fi
    sleep 0.25
  done

  echo "[Control] $name did not stop in time; forcing shutdown."
  kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  rm -f "$path"
}

show_status() {
  local harness_pid runtime_pid
  harness_pid="$(read_pid "$HARNESS_PID")"
  runtime_pid="$(read_pid "$FREETOKEN_PID")"

  echo "=== Local MoE Harness Status ==="
  if pid_alive "$harness_pid"; then
    echo "Harness process:  running (PID $harness_pid)"
  else
    echo "Harness process:  not managed/running"
  fi
  if pid_alive "$runtime_pid"; then
    echo "FreeToken process: running (PID $runtime_pid)"
  else
    echo "FreeToken process: not managed/running"
  fi

  python3 - "$HARNESS_URL" <<'PY'
import json
import sys
import urllib.request

base = sys.argv[1]
try:
    with urllib.request.urlopen(base + "/api/status", timeout=3) as response:
        data = json.load(response)
except Exception as exc:
    print(f"Harness HTTP:      offline/unreachable ({exc})")
    raise SystemExit(0)

runtime = data.get("runtime") or {}
settings = data.get("settings") or {}
models = runtime.get("models") or []
model = models[0].get("id") if models else "unknown"
phase = runtime.get("phase") or runtime.get("health_status") or "unknown"
capacity = settings.get("conversation_kv_floor_tokens")
profile = "custom"
if capacity == 12288:
    profile = "balanced12k"
elif capacity == 8192:
    profile = "fast8k"
elif capacity == 4096:
    profile = "4k"
print("Harness HTTP:      online")
print(f"FreeToken ready:   {bool(runtime.get('ready'))}")
print(f"Runtime phase:     {phase}")
print(f"Model:             {model}")
print(f"Context profile:   {profile}")
print(f"Context capacity:  {capacity if capacity is not None else 'unknown'} tokens")
print(f"Chat URL:          {base}")
PY

  if [[ -f "$STATE_DIR/startup-performance.json" ]]; then
    python3 - "$STATE_DIR/startup-performance.json" <<'PY'
import json
import sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text())
except Exception:
    raise SystemExit(0)
perf = data.get("performance") or data.get("primer") or {}
print(f"Startup gate:      {data.get('status', 'unknown')}")
if perf.get("ttft_s") is not None:
    print(f"Gate TTFT:         {perf['ttft_s']:.2f}s")
if perf.get("decode_tps") is not None:
    print(f"Gate decode:       {perf['decode_tps']:.2f} tok/s")
PY
  fi

  if [[ -f "$STATE_DIR/context-safety.json" ]]; then
    python3 - "$STATE_DIR/context-safety.json" <<'PY'
import json
import sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text())
except Exception:
    raise SystemExit(0)
result = data.get("result") or {}
print(f"Context gate:      {data.get('status', 'unknown')}")
if result.get("counted_prompt_tokens") is not None:
    print(f"Cold prompt test:  {result['counted_prompt_tokens']} tokens")
PY
  fi
}

capture_diagnostics() {
  local label="$1"
  local stamp out
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  out="$LOG_DIR/degraded-startup-${stamp}-${label}.log"
  {
    echo "Local MoE degraded startup diagnostics"
    echo "timestamp_utc=$stamp"
    echo "label=$label"
    echo "context_profile=${LOCAL_MOE_CONTEXT_PROFILE:-unknown}"
    echo "kv_reserve=${LOCAL_MOE_KV_RESERVE_TOKENS:-unknown}"
    echo "max_prefill=${LOCAL_MOE_MAX_PREFILL_LENGTH:-unknown}"
    echo "prefill_hit_d2d=${LOCAL_MOE_PREFILL_HIT_D2D:-unknown}"
    echo
    echo "--- startup performance ---"
    cat "$STATE_DIR/startup-performance.json" 2>/dev/null || true
    echo
    echo "--- context safety ---"
    cat "$STATE_DIR/context-safety.json" 2>/dev/null || true
    echo
    echo "--- GPU ---"
    nvidia-smi --query-gpu=name,pstate,utilization.gpu,memory.used,memory.total,power.draw,power.limit,temperature.gpu,clocks.sm,clocks.mem --format=csv,noheader 2>&1 || true
    echo
    echo "--- memory ---"
    free -h 2>&1 || true
    echo
    echo "--- load ---"
    uptime 2>&1 || true
    echo
    echo "--- relevant FreeToken log lines ---"
    grep -E "Auto-selected|Resolved config|benchbw|moe-cache|hybrid-max-fetch|CPU MoE executor|flag handshake|cudaLaunchHostFunc|stream memory|memory-ratio|Memory ratio|BW profile|Startup mode|max_extend_tokens|moe_prefill_hit_d2d|Prefill" \
      "$LOG_DIR/freetoken-server.log" 2>/dev/null | tail -n 160 || true
    echo
    echo "--- FreeToken log tail ---"
    tail -n 100 "$LOG_DIR/freetoken-server.log" 2>/dev/null || true
  } >"$out"
  echo "[Control] Saved degraded-startup diagnostics: $out"
}

run_performance_gate() {
  local startup_timeout
  startup_timeout="${LOCAL_MOE_STARTUP_TIMEOUT:-$(registry_startup_budget)}"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/warmup-harness.py" \
    --timeout "$startup_timeout" \
    --request-timeout "${LOCAL_MOE_GATE_REQUEST_TIMEOUT:-45}" \
    --max-primer-total "${LOCAL_MOE_GATE_MAX_PRIMER_TOTAL:-20}" \
    --max-ttft "${LOCAL_MOE_GATE_MAX_TTFT:-12}" \
    --min-decode-tps "${LOCAL_MOE_GATE_MIN_DECODE_TPS:-4}" \
    --max-total "${LOCAL_MOE_GATE_MAX_TOTAL:-40}"
}

run_context_gate() {
  local kv="${LOCAL_MOE_KV_RESERVE_TOKENS:-4096}"
  if [[ "${LOCAL_MOE_LONG_CONTEXT_GATE:-1}" == "0" ]]; then
    echo "[Control] Long-context safety gate disabled by LOCAL_MOE_LONG_CONTEXT_GATE=0."
    return 0
  fi
  if (( kv < 6144 )); then
    echo "[Control] Context profile is <=4K; long-context cold-prefill gate not required."
    return 0
  fi

  echo "[Control] Verifying chunked cold-prefill safety before opening the ${LOCAL_MOE_CONTEXT_PROFILE:-selected} chat..."
  "$ROOT/.venv/bin/python" "$ROOT/scripts/validate-long-context.py" \
    --target-tokens "${LOCAL_MOE_CONTEXT_GATE_TOKENS:-6800}" \
    --kv-reserve "$kv" \
    --max-prefill "${LOCAL_MOE_MAX_PREFILL_LENGTH:-2048}" \
    --d2d "${LOCAL_MOE_PREFILL_HIT_D2D:-1}" \
    --timeout "${LOCAL_MOE_CONTEXT_GATE_TIMEOUT:-120}"
}

stop_all() {
  stop_pidfile "$HARNESS_PID" "Harness"
  stop_pidfile "$FREETOKEN_PID" "FreeToken"
}

start_all() {
  local attempt=1
  local requested_profile="${LOCAL_MOE_CONTEXT_PROFILE:-balanced12k}"
  local selected_model default_model
  unset LOCAL_MOE_RECOVERY 2>/dev/null || true

  echo "[Control] Verifying pinned FreeToken runtime..."
  "$ROOT/scripts/verify-freetoken-runtime.sh"

  if [[ "$requested_profile" == "balanced12k" && "${LOCAL_MOE_ALLOW_BUSY_12K:-0}" != "1" ]]; then
    if gpu_busy_preflight; then
      echo "[Control] External GPU load detected before startup; using validated Fast 8K profile for this run."
      echo "[Control] Set LOCAL_MOE_ALLOW_BUSY_12K=1 only for controlled 12K-under-load testing."
      requested_profile="fast8k"
    fi
  fi

  configure_context_profile "$requested_profile" || return $?

  while (( attempt <= 2 )); do
    if (( attempt == 2 )); then
      configure_recovery_profile
      echo
      echo "[Control] Recovery attempt: switching to the selected model's conservative recovery profile."
    fi

    selected_model="$($ROOT/.venv/bin/python "$ROOT/scripts/model-selection.py" selected)"
    default_model="$($ROOT/.venv/bin/python "$ROOT/scripts/model-selection.py" default)"
    if [[ "$selected_model" == "$default_model" ]]; then
      echo "[Control] Startup preference: ${LOCAL_MOE_CONTEXT_PROFILE} (the lifecycle will recheck GPU load)."
      echo "[Control] KV=${LOCAL_MOE_KV_RESERVE_TOKENS}, prefill chunk=${LOCAL_MOE_MAX_PREFILL_LENGTH}, D2D=${LOCAL_MOE_PREFILL_HIT_D2D}"
    else
      echo "[Control] Selected model: ${selected_model}; model-specific $(startup_profile_name) geometry will be resolved by the registry."
    fi
    start_harness
    sync_profile_from_harness
    sync_context_gate_from_active_profile
    echo "[Control] Active model profile: ${LOCAL_MOE_CONTEXT_PROFILE} (KV=${LOCAL_MOE_KV_RESERVE_TOKENS}, prefill=${LOCAL_MOE_MAX_PREFILL_LENGTH}, D2D=${LOCAL_MOE_PREFILL_HIT_D2D})"

    if harness_waiting_for_model; then
      echo
      echo "[Control] READY - Harness UI is online; the selected checkpoint is not installed."
      echo "[Control] Install a supported model from the terminal, then choose it in the model selector."
      echo "[Control] URL: http://localhost:5180"
      return 0
    fi

    echo "[Control] Waiting for FreeToken readiness, warming kernels, and checking real chat speed..."

    if run_performance_gate && run_context_gate; then
      echo
      if (( attempt == 2 )); then
        echo "[Control] READY - Local MoE recovered on the selected model's recovery profile."
      else
        echo "[Control] READY - Local MoE passed speed and context-safety gates."
      fi
      echo "[Control] Active profile: ${LOCAL_MOE_CONTEXT_PROFILE}"
      echo "[Control] URL: http://localhost:5180"
      return 0
    fi

    capture_diagnostics "attempt${attempt}"

    if (( attempt == 1 )); then
      echo
      echo "[Control] Primary startup did not pass all safety gates."
      echo "[Control] Performing one clean automatic restart on the selected model's recovery profile."
      stop_all
      sleep 2
      attempt=2
      continue
    fi

    echo
    selected_model="$($ROOT/.venv/bin/python "$ROOT/scripts/model-selection.py" selected)"
    default_model="$($ROOT/.venv/bin/python "$ROOT/scripts/model-selection.py" default)"
    if [[ "$selected_model" != "$default_model" ]]; then
      echo "[Control] Alternate model $selected_model did not pass startup gates."
      echo "[Control] Restoring the default Qwen model on its verified recovery profile."
      stop_all
      "$ROOT/.venv/bin/python" "$ROOT/scripts/model-selection.py" select-default >/dev/null
      configure_recovery_profile
      start_harness
      sync_profile_from_harness
      echo "[Control] Default recovery profile: ${LOCAL_MOE_CONTEXT_PROFILE} (KV=${LOCAL_MOE_KV_RESERVE_TOKENS}, prefill=${LOCAL_MOE_MAX_PREFILL_LENGTH}, D2D=${LOCAL_MOE_PREFILL_HIT_D2D})"
      if run_performance_gate && run_context_gate; then
        echo
        echo "[Control] READY - Restored the default Qwen model after alternate startup failure."
        echo "[Control] Active profile: ${LOCAL_MOE_CONTEXT_PROFILE}"
        echo "[Control] URL: http://localhost:5180"
        return 0
      fi
      capture_diagnostics "default-recovery"
    fi

    echo "[Control] ERROR: Local MoE remained unhealthy after the verified fallback attempt."
    echo "[Control] The browser will NOT be opened."
    echo "[Control] Check the degraded-startup log under: $LOG_DIR"
    stop_all
    return 1
  done
}

case "${1:-}" in
  start)
    start_all
    ;;
  start-12k)
    export LOCAL_MOE_CONTEXT_PROFILE=balanced12k
    start_all
    ;;
  start-8k)
    export LOCAL_MOE_CONTEXT_PROFILE=fast8k
    start_all
    ;;
  start-4k)
    export LOCAL_MOE_CONTEXT_PROFILE=balanced4k
    start_all
    ;;
  status)
    show_status
    ;;
  stop)
    stop_all
    ;;
  *)
    echo "Usage: $0 {start|start-12k|start-8k|start-4k|status|stop}"
    exit 2
    ;;
esac
