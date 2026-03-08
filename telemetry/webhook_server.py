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
    
    # 2. Extract PID, MLFQ Priority score, and Action Type
    rogue_pid = data.get('pid')
    mlfq_priority = data.get('mlfq_priority', 0)  # Default to 0 (highest threat) if missing
    action_type = data.get('action_type', 0)      # Default to 0 (neutralize) if missing
    
    if not rogue_pid:
        print(f"\n[!] ALERT RECEIVED FROM ML ANALYZER: {data.get('description', 'No description')} ")
        print("No PID specified in the alert, nothing to kill.")
        return jsonify({"status": "ignored", "reason": "no pid"}), 200

    if rogue_pid and rogue_pid.isdigit():
        print(f"[*] Targeting Rogue PID: {rogue_pid} with MLFQ Priority {mlfq_priority} & Action {action_type}")
        try:
            # Note: We must invoke the C++ compiled binary Handler to trigger the MLFQ queue preemption natively
            # The C++ source is built into /app/interceptor/mlfq_handler by the Dockerfile
            
            # Pass the PID, Priority, and ActionType to the C++ Handler
            result = subprocess.run(
                [HANDLER_BIN, str(rogue_pid), str(mlfq_priority), str(action_type)], 
                capture_output=True, 
                text=True
            )
            
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

        except Exception as e:
            print(f"[!] MLFQ Handler failed execution: {e}")
            return jsonify({"status": "error", "reason": "mlfq_handler_failed"}), 500
        
    return jsonify({"error": "No active Agent PID found."}), 404

if __name__ == '__main__':
    # Run heavily isolated on a non-standard port so it doesn't conflict with Mac AirPlay receiver
    # Must bind to 0.0.0.0 so Docker can expose it to the host machine
    app.run(host='0.0.0.0', port=5005)
