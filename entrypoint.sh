#!/bin/bash
set -e

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

exec python3 /app/telemetry/wrapper.py \
  node /app/openclaw/dist/index.js gateway \
  --port 18789 \
  --allow-unconfigured
