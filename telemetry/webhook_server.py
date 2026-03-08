#!/usr/bin/env python3
from flask import Flask, request, jsonify
import subprocess
import os
import requests

app = Flask(__name__)

# The path to the compiled MLFQ Handler C++ binary
HANDLER_BIN = "/app/interceptor/mlfq_handler"

@app.route('/splunk-alert', methods=['POST'])
def handle_alert():
    data = request.json
    print(f"[*] ALARM: Received Webhook from Splunk Edge Pipeline.")
    print(f"[*] Payload: {data}")
    
    import tempfile
    
    try:
        temp_dir = tempfile.gettempdir()
    except FileNotFoundError:
        os.makedirs('/tmp', exist_ok=True)
        tempfile.tempdir = '/tmp'
        temp_dir = '/tmp'
        
    pid_file = os.path.join(temp_dir, "openclaw.pid")
    
    # We retrieve the PID of the OpenClaw wrapper we saved earlier
    try:
        with open(pid_file, "r") as f:
            target_pid = f.read().strip()
            
        if not target_pid:
            print("No PID specified in the alert, nothing to kill.")
            return jsonify({"status": "ignored", "reason": "no pid"}), 200

        # Execute the C++ MLFQ Handler to kill the rogue process AND trigger rollback
        try:
            print(f"[*] Splunk Triggered Kill Switch for Rogue PID: {target_pid}")
            # Call Yash's C++ handler synchronously
            subprocess.run([HANDLER_BIN, str(target_pid)], check=True)
            
            # Increment the Threat Counter on the React Dashboard via Firebase
            firebase_url = "https://openclaw-sentinal-default-rtdb.firebaseio.com/stats/threatsNeutralized.json"
            
            try:
                # Get current count
                resp = requests.get(firebase_url)
                current_count = resp.json() if resp.text != 'null' else 0
                if current_count is None:
                    current_count = 0
                
                # Update count
                requests.put(firebase_url, json=current_count + 1)
                print(f"[*] Updated Firebase Threat Count to: {current_count + 1}")
            except Exception as e:
                print(f"[!] Failed to update Firebase UI: {e}")

            return jsonify({"status": "success", "action": "mlfq_handler_invoked"}), 200

        except subprocess.CalledProcessError as e:
            print(f"[!] MLFQ Handler failed execution: {e}")
            return jsonify({"status": "error", "reason": "mlfq_handler_failed"}), 500
        
    except FileNotFoundError:
        return jsonify({"error": "No active Agent PID found."}), 404

if __name__ == '__main__':
    # Run heavily isolated on a non-standard port so it doesn't conflict with Mac AirPlay receiver
    # Must bind to 0.0.0.0 so Docker can expose it to the host machine
    app.run(host='0.0.0.0', port=5005)
