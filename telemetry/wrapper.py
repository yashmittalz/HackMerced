#!/usr/bin/env python3
import subprocess
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime

# Splunk Cloud HTTP Event Collector (HEC) Configuration
SPLUNK_HEC_URL = os.environ.get("SPLUNK_HEC_URL", "https://http-inputs-prd-p-vkh7t.splunkcloud.com/services/collector/event")
SPLUNK_HEC_TOKEN = os.environ.get("SPLUNK_HEC_TOKEN", "6f0b0636-8da4-478c-a4a6-7c5d800127cd")

def send_to_splunk(log_line):
    """Chunks the stdout and fires it to Splunk HEC over Wi-Fi"""
    try:
        payload = {
            "time": datetime.now().timestamp(),
            "sourcetype": "_json",
            "event": {
                "message": log_line.strip(),
                "source": "openclaw_stdout"
            }
        }
        
        req = urllib.request.Request(
            SPLUNK_HEC_URL, 
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Authorization": f"Splunk {SPLUNK_HEC_TOKEN}",
                "Content-Type": "application/json"
            }
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
    # Save our own PID to a file so the webhook listener knows what to kill
    with open(pid_file, "w") as f:
        f.write(str(os.getpid()))
        
    # Boot the Flask Webhook Server in the background to listen for Splunk kill switches
    print("[*] Booting Webhook Listener on port 5005...")
    webhook_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webhook_server.py")
    subprocess.Popen([sys.executable if sys.executable else "python", webhook_script])
        
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
            send_to_splunk(line)
        
    process.wait()

if __name__ == "__main__":
    main()
