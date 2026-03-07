#!/usr/bin/env python3
import subprocess
import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime

# Splunk Cloud HTTP Event Collector (HEC) Configuration
SPLUNK_HEC_URL = os.environ.get("SPLUNK_HEC_URL", "https://your-splunk-cloud.com:8088/services/collector/event")
SPLUNK_HEC_TOKEN = os.environ.get("SPLUNK_HEC_TOKEN", "YOUR_SPLUNK_TOKEN")

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
    
    # Save our own PID to a file so the webhook listener knows what to kill
    with open("/tmp/openclaw.pid", "w") as f:
        f.write(str(os.getpid()))
        
    # Boot the Flask Webhook Server in the background to listen for Splunk kill switches
    print("[*] Booting Webhook Listener on port 5005...")
    subprocess.Popen(["python3", "/app/telemetry/webhook_server.py"])
        
    # Start the subprocess with LD_PRELOAD injected via the environment
    # Note: LD_PRELOAD should already be in the ENVs passed from the Dockerfile
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Continuously read and tee the output
    for line in iter(process.stdout.readline, ''):
        sys.stdout.write(line)
        sys.stdout.flush()
        send_to_splunk(line)
        
    process.wait()

if __name__ == "__main__":
    main()
