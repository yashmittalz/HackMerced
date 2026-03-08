#!/usr/bin/env python3
import subprocess
import os
import sys
import json
import urllib.request
import urllib.parse
import threading
import time
from datetime import datetime

# ML Analyzer Ingestion Endpoint
ML_ANALYZER_URL = "http://localhost:5006/analyze"

def send_to_ml_analyzer(log_line, pid):
    """Chunks the stdout and fires it to our local ML engine for AI Priority Analysis"""
    try:
        payload = {
            "time": datetime.now().timestamp(),
            "sourcetype": "_json",
            "event": {
                "message": log_line.strip(),
                "source": "openclaw_stdout",
                "pid": pid
            }
        }
        
        req = urllib.request.Request(
            ML_ANALYZER_URL, 
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        # Failsafe: if telemetry fails, do not crash the wrapper
        pass

def increment_telemetry_stat():
    """Increments the total_telemetry counter in Firebase"""
    try:
        url = "https://openclaw-sentinal-default-rtdb.firebaseio.com/stats/telemetry_events.json"
        req = urllib.request.Request(
            url, 
            data=json.dumps({"ts": datetime.now().timestamp()}).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=0.5)
    except Exception:
        pass

def extract_readable_log(line):
    """
    OpenClaw writes structured JSON log lines. Parse them and extract
    only the human-readable message text so the ML model and dashboard
    don't receive raw JSON blobs.
    Returns None if the line should be skipped entirely.
    """
    stripped = line.strip()
    if not stripped or len(stripped) < 5:
        return None
    
    # Try to parse as JSON (OpenClaw structured log format)
    try:
        obj = json.loads(stripped)
        
        # Skip DEBUG level logs — they're internal cron/heartbeat noise
        log_level = obj.get("_meta", {}).get("logLevelName", "")
        if log_level in ("DEBUG", "TRACE", "VERBOSE"):
            return None
        
        # Extract human-readable message fields
        # OpenClaw JSON logs put the message in numeric string keys "0", "1", "2"...
        parts = []
        for key in sorted(obj.keys()):
            if key.startswith("_") or key == "time":
                continue
            val = obj[key]
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, (int, float, bool)):
                pass  # skip raw numbers
        
        if parts:
            message = " | ".join(p for p in parts if p.strip())
            return message if message else None
        
        # Fallback: check for a top-level 'msg' or 'message' field
        for field in ("msg", "message", "text"):
            if field in obj and isinstance(obj[field], str):
                return obj[field]
        
        return None  # Skip unreadable structured logs
        
    except (json.JSONDecodeError, ValueError):
        # Plain text line — return as-is
        return stripped

def tail_log_file(log_path, pid):
    """
    Tails the OpenClaw gateway log file and sends NEW lines to ml_analyzer.
    This captures the ACTUAL conversation content (including AI responses)
    which never appears in stdout — only in the log file.
    """
    print(f"[*] Log Tail Thread: watching {log_path} for AI output...")
    
    # Wait for the log file to be created
    for _ in range(30):
        if os.path.exists(log_path):
            break
        time.sleep(1)
    
    if not os.path.exists(log_path):
        print(f"[!] Log Tail Thread: log file not found at {log_path}, skipping.")
        return
    
    # Open and seek to the end (we don't want old content, only new lines)
    with open(log_path, 'r', errors='replace') as f:
        f.seek(0, 2)  # Seek to end of file
        while True:
            line = f.readline()
            if line:
                readable = extract_readable_log(line)
                if readable:
                    send_to_ml_analyzer(readable, pid)
            else:
                time.sleep(0.2)  # Tiny sleep to avoid busy-looping

def main():
    if len(sys.argv) < 2:
        print("Usage: wrapper.py <command_to_wrap>")
        sys.exit(1)
        
    command = sys.argv[1:]
    print(f"[*] Starting Semantic Firewall Telemetry Wrapper around: {' '.join(command)}")
    
    import tempfile
    
    # In some minimalistic docker containers, standard temp directories may not exist
    try:
        temp_dir = tempfile.gettempdir()
    except FileNotFoundError:
        os.makedirs('/tmp', exist_ok=True)
        tempfile.tempdir = '/tmp'
        temp_dir = '/tmp'
        
    pid_file = os.path.join(temp_dir, "openclaw.pid")
    openclaw_pid = str(os.getpid())
    # Save our own PID to a file so the webhook listener knows what to kill
    with open(pid_file, "w") as f:
        f.write(openclaw_pid)
        
    # NOTE: Webhook server is started by entrypoint.sh before this wrapper runs.
    # Do NOT start it again here — it would conflict on port 5005.
    print("[*] Webhook Listener on port 5005 already running (started by entrypoint.sh).")
    
    # Start the subprocess with LD_PRELOAD injected via the environment
    cmd_to_run = command if os.name != 'nt' else " ".join(command)
    
    # Explicitly inject the C++ Security Hook here, nowhere else
    child_env = os.environ.copy()
    child_env["LD_PRELOAD"] = "/app/interceptor/hook.so"

    process = subprocess.Popen(
        cmd_to_run,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(os.name == 'nt'),
        env=child_env
    )
    
    # Start the log file tail watcher in a background thread
    # This feeds the actual AI conversation content to ml_analyzer
    log_path = f"/tmp/openclaw/openclaw-{datetime.now().strftime('%Y-%m-%d')}.log"
    log_thread = threading.Thread(target=tail_log_file, args=(log_path, openclaw_pid), daemon=True)
    log_thread.start()
    
    # Continuously read and tee the stdout (system-level events, LD_PRELOAD hooks, etc.)
    if process.stdout:
        for line in iter(process.stdout.readline, ''):
            sys.stdout.write(line)
            sys.stdout.flush()
            send_to_ml_analyzer(line, openclaw_pid)
            increment_telemetry_stat()
        
    process.wait()

if __name__ == "__main__":
    main()
