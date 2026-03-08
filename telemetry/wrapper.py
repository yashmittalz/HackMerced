#!/usr/bin/env python3
import subprocess
import os
import sys
import json
import urllib.request
import urllib.parse
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
        
        # In a real environment, you'd want to handle SSL properly or keep a session open.
        urllib.request.urlopen(req, timeout=1)
    except Exception as e:
        # Failsafe: if telemetry fails, do not crash the wrapper
        pass

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
    # Note: LD_PRELOAD should already be in the ENVs passed from the Dockerfile
    
    # On Windows, we need to pass the arguments as a flat string if shell=True is used,
    # or keep it as a list but allow `subprocess` to find the executable.
    cmd_to_run = command if os.name != 'nt' else " ".join(command)
    process = subprocess.Popen(
        cmd_to_run,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        shell=(os.name == 'nt')
    )
    
    # Continuously read and tee the output
    if process.stdout:
        for line in iter(process.stdout.readline, ''):
            sys.stdout.write(line)
            sys.stdout.flush()
            send_to_ml_analyzer(line, openclaw_pid)
        
    process.wait()

if __name__ == "__main__":
    main()
