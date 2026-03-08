#!/bin/bash
# Note: No 'set -e' — we manage errors manually since we background multiple processes

# ============================================================
#  OpenBot Semantic Firewall — Container Entrypoint
#  Boots security APIs first, then hands off to OpenClaw.
#  Acts as the single ordered orchestrator for all services.
# ============================================================

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       OpenBot Semantic Firewall Starting...      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ----------------------------------------------------------
# Helper: block until a local TCP port is accepting connections
# Uses pure bash /dev/tcp — no curl/nc dependency needed.
# ----------------------------------------------------------
wait_for_port() {
  local port=$1
  local label=$2
  local attempts=0
  local max=30
  echo "[*] Waiting for $label to be ready on port $port..."
  until (echo > /dev/tcp/localhost/$port) 2>/dev/null; do
    attempts=$((attempts + 1))
    if [ $attempts -ge $max ]; then
      echo "[!] FATAL: $label never came up on port $port after ${max}s. Aborting."
      exit 1
    fi
    sleep 1
  done
  echo "[+] $label is UP on port $port."
}

# ----------------------------------------------------------
# Step 1: Boot the ML Threat Analyzer (port 5006)
# This MUST be ready before wrapper.py starts streaming logs.
# ----------------------------------------------------------
echo "[1/3] Starting ML Threat Analyzer (port 5006)..."
python3 /app/telemetry/ml_analyzer.py &
ML_PID=$!
wait_for_port 5006 "ML Threat Analyzer"

# ----------------------------------------------------------
# Step 2: Boot the Webhook Server / C++ Trigger (port 5005)
# ----------------------------------------------------------
echo "[2/3] Starting Webhook Server (port 5005)..."
python3 /app/telemetry/webhook_server.py &
WEBHOOK_PID=$!
wait_for_port 5005 "Webhook Server"

# ----------------------------------------------------------
# Step 3: Detect first-run vs configured state
# OpenClaw stores its config in ~/.openclaw (volume-mounted).
# ----------------------------------------------------------
OPENCLAW_CONFIG="$HOME/.openclaw"
echo ""
if [ ! -d "$OPENCLAW_CONFIG" ] || [ -z "$(ls -A $OPENCLAW_CONFIG 2>/dev/null)" ]; then
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  FIRST RUN DETECTED — OpenClaw Onboarding Required          ║"
  echo "║                                                              ║"
  echo "║  Complete the onboarding wizard below. Your config will be  ║"
  echo "║  saved to ~/.openclaw and persisted on your host machine.   ║"
  echo "║  Subsequent runs will skip this step entirely.              ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
else
  echo "[+] OpenClaw config found at $OPENCLAW_CONFIG — skipping onboarding."
fi

# ----------------------------------------------------------
# Step 4: Exec into wrapper.py → OpenClaw
# Using 'exec' replaces this shell and makes Python PID 1.
# This ensures SIGTERM from docker stop is handled cleanly.
# The wrapper intercepts ALL OpenClaw stdout in real-time.
# ----------------------------------------------------------
echo ""
echo "[3/3] Handing off to OpenClaw via Telemetry Wrapper..."
echo "      All stdout is being intercepted by the Semantic Firewall."
echo ""

# ------------------------------------------------------------------
# Step 4: Launch wrapper.py (which runs OpenClaw) in the background
# We cannot use 'exec ... &' — exec replaces the shell (PID 1) and
# cannot be backgrounded. Instead: run as a normal subprocess.
# ------------------------------------------------------------------
python3 /app/telemetry/wrapper.py \
  node /app/openclaw/dist/index.js gateway \
  --port 18789 \
  --allow-unconfigured &
OPENCLAW_PID=$!

# Wait for the gateway to start (it binds to 127.0.0.1:18789)
echo "[*] Waiting for OpenClaw gateway on 127.0.0.1:18789..."
WAIT_COUNT=0
until (echo > /dev/tcp/localhost/18789) 2>/dev/null; do
  sleep 1
  WAIT_COUNT=$((WAIT_COUNT + 1))
  if [ $WAIT_COUNT -ge 30 ]; then
    echo "[!] Timed out waiting for OpenClaw on 18789 — gateway may not be running."
    break
  fi
done

if (echo > /dev/tcp/localhost/18789) 2>/dev/null; then
  echo "[+] OpenClaw gateway UP on 18789."
  # Bridge loopback (127.0.0.1:18789) to all interfaces on 18790
  echo "[*] Starting socat bridge: 0.0.0.0:18790 → 127.0.0.1:18789"
  socat TCP-LISTEN:18790,fork,reuseaddr TCP:127.0.0.1:18789 &
fi

# Wait for the browser/server to start (it binds to 127.0.0.1:18791)
echo "[*] Waiting for OpenClaw browser server on 127.0.0.1:18791..."
WAIT_COUNT=0
until (echo > /dev/tcp/localhost/18791) 2>/dev/null; do
  sleep 1
  WAIT_COUNT=$((WAIT_COUNT + 1))
  if [ $WAIT_COUNT -ge 30 ]; then
    echo "[!] Timed out waiting for OpenClaw on 18791 — browser server may not be running."
    break
  fi
done

if (echo > /dev/tcp/localhost/18791) 2>/dev/null; then
  echo "[+] OpenClaw browser server UP on 18791."
  # Bridge loopback (127.0.0.1:18791) to all interfaces on 18800
  # Docker maps external 18792 → internal 18800 (cannot use 18792 internally
  # because Docker Desktop pre-occupies the container-side of mapped ports)
  echo "[*] Starting socat bridge: 0.0.0.0:18800 → 127.0.0.1:18791"
  socat TCP-LISTEN:18800,fork,reuseaddr TCP:127.0.0.1:18791 &
  sleep 1
  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║  OpenClaw is READY                                           ║"
  echo "║                                                              ║"
  echo "║  Control UI: http://localhost:18789/                         ║"
  echo "║  (Auth is disabled so browser can access it directly)        ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo ""
fi

wait $OPENCLAW_PID
