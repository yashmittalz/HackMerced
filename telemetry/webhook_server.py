#!/usr/bin/env python3
from flask import Flask, request, jsonify
import subprocess
import os

app = Flask(__name__)

# The path to the compiled MLFQ Handler C++ binary
HANDLER_BIN = "/app/interceptor/mlfq_handler"

@app.route('/splunk-alert', methods=['POST'])
def handle_alert():
    data = request.json
    print(f"[*] ALARM: Received Webhook from Splunk Edge Pipeline.")
    print(f"[*] Payload: {data}")
    
    # We retrieve the PID of the OpenClaw wrapper we saved earlier
    try:
        with open("/tmp/openclaw.pid", "r") as f:
            target_pid = f.read().strip()
            
        print(f"[*] Routing termination order for PID: {target_pid} to C++ MLFQ Handler...")
        
        # Call the blazing fast C++ binary to execute the Kill/Rollback sequence
        subprocess.run([HANDLER_BIN, target_pid])
        
        # Extra points: You would typically shoot a pulse to Firebase here for the React UI
        # e.g., requests.post("https://your-firebase-db.firebaseio.com/incidents.json", json={"status": "neutralized"})
        
        return jsonify({"status": "intercepted_and_neutralized", "pid": target_pid}), 200
        
    except FileNotFoundError:
        return jsonify({"error": "No active Agent PID found."}), 404

if __name__ == '__main__':
    # Listen on all interfaces so the Docker container can expose port 5000 
    # and receive Ngrok/Tailscale tunnels returning from Splunk Cloud.
    app.run(host='0.0.0.0', port=5000)
