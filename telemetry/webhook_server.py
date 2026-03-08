#!/usr/bin/env python3
from flask import Flask, request, jsonify
import subprocess
import os
import requests

import threading
import time

app = Flask(__name__)

# Load configuration from environment
FIREBASE_DB_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://openclaw-sentinal-default-rtdb.firebaseio.com")
STATS_URL = f"{FIREBASE_DB_URL}/stats/threatsNeutralized.json"
HISTORY_URL = f"{FIREBASE_DB_URL}/threat_history.json"
ACTIVE_URL = f"{FIREBASE_DB_URL}/active_threats.json"

# The path to the compiled MLFQ Handler C++ binary
HANDLER_BIN = "/app/interceptor/mlfq_handler"

def delete_after_delay(url, delay=5):
    """Wait for the delay then delete the record from Firebase."""
    time.sleep(delay)
    try:
        requests.delete(url)
        print(f"[*] Cleaned up active threat: {url}")
    except Exception as e:
        print(f"[!] Cleanup failed: {e}")

def consolidate_stats():
    """Periodically consolidates event-based stats into single counters."""
    while True:
        try:
            # Consolidate Quarantine Events
            resp = requests.get(f"{FIREBASE_DB_URL}/stats/quarantine_events.json")
            events = resp.json()
            if events:
                count = len(events)
                requests.patch(f"{FIREBASE_DB_URL}/stats.json", json={"total_quarantined": count})
            
            # Consolidate Telemetry Events
            resp = requests.get(f"{FIREBASE_DB_URL}/stats/telemetry_events.json")
            events = resp.json()
            if events:
                count = len(events)
                requests.patch(f"{FIREBASE_DB_URL}/stats.json", json={"total_telemetry": count})
                
            # Update Uptime (assuming startTime is when the server started)
            uptime = int(time.time() - START_TIME)
            requests.patch(f"{FIREBASE_DB_URL}/stats.json", json={"uptime_seconds": uptime})
            
        except Exception as e:
            print(f"[!] Consolidation failed: {e}")
        time.sleep(10) # Run every 10 seconds

START_TIME = time.time()
threading.Thread(target=consolidate_stats, daemon=True).start()

@app.route('/splunk-alert', methods=['POST'])
def handle_alert():
    data = request.json
    print(f"[*] ALARM: Received Webhook from Splunk Edge Pipeline.")
    print(f"[*] Payload: {data}")
    
    # Track Total Received
    try:
        requests.patch(f"{FIREBASE_DB_URL}/stats.json", json={
            "total_received": requests.get(f"{FIREBASE_DB_URL}/stats/total_received.json").json() + 1 if requests.get(f"{FIREBASE_DB_URL}/stats/total_received.json").text != 'null' else 1
        })
    except Exception:
        pass

    import tempfile
    
    try:
        temp_dir = tempfile.gettempdir()
    except FileNotFoundError:
        os.makedirs('/tmp', exist_ok=True)
        temp_dir = '/tmp'
        
    pid_file = os.path.join(temp_dir, "openclaw.pid")
    
    # 2. Extract PID, MLFQ Priority score, and Action Type
    rogue_pid = data.get('pid')
    mlfq_priority = data.get('mlfq_priority', 0)
    action_type = data.get('action_type', 0)
    description = data.get('description', 'Unknown malicious activity')
    source = data.get('source', 'Unknown Vector')
    
    if not rogue_pid:
        print(f"\n[!] ALERT RECEIVED FROM ML ANALYZER: {description} ")
        print("No PID specified in the alert, nothing to kill.")
        return jsonify({"status": "ignored", "reason": "no pid"}), 200

    if rogue_pid and (isinstance(rogue_pid, int) or rogue_pid.isdigit()):
        print(f"[*] Targeting Rogue PID: {rogue_pid} with MLFQ Priority {mlfq_priority} & Action {action_type}")
        
        # Prepare threat record for Firebase
        threat_record = {
            "pid_killed": rogue_pid,
            "threat_level": "CRITICAL" if mlfq_priority == 0 else "HIGH",
            "action_taken": "Mitigating...",
            "agent_thought": description,
            "vector": source,
            "timestamp": time.time(),
            "status": "active"
        }

        # 1. Log to history (persistent)
        try:
            requests.post(HISTORY_URL, json=threat_record)
        except Exception as e:
            print(f"[!] Failed to log to history: {e}")

        # 2. Add to active threats (real-time)
        active_key = None
        try:
            resp = requests.post(ACTIVE_URL, json=threat_record)
            active_key = resp.json().get('name')
        except Exception as e:
            print(f"[!] Failed to log to active threats: {e}")

        try:
            # 3. Invoke the C++ compiled binary Handler
            start_time = time.time()
            result = subprocess.run(
                [HANDLER_BIN, str(rogue_pid), str(mlfq_priority), str(action_type)], 
                capture_output=True, 
                text=True
            )
            latency_ms = int((time.time() - start_time) * 1000)
            
            # 3.5 Broadcast MLFQ C++ stdout to Firebase for Web UI live terminal
            if result.stdout:
                print(f"[+] Relaying MLFQ Stdout to Live Trace...")
                try:
                    logs = result.stdout.strip().split('\n')
                    requests.post(f"{FIREBASE_DB_URL}/mlfq_live_trace.json", json={
                        "timestamp": time.time(),
                        "pid": rogue_pid,
                        "logs": logs
                    })
                except Exception as e:
                    print(f"[!] Failed to push MLFQ trace: {e}")
            
            # Update Dashboard Status
            try:
                # Update threat count and latency stats
                resp = requests.get(f"{FIREBASE_DB_URL}/stats.json")
                stats = resp.json() if resp and resp.text != 'null' else {}
                
                current_count = stats.get('threatsNeutralized', 0)
                total_latency = stats.get('total_latency_ms', 0)
                total_solved = stats.get('total_solved', 0)
                
                new_count = (current_count or 0) + 1
                new_total_latency = (total_latency or 0) + latency_ms
                new_total_solved = (total_solved or 0) + (1 if action_type == 0 else 0)
                avg_latency = int(new_total_latency / new_count) if new_count > 0 else 0

                requests.patch(f"{FIREBASE_DB_URL}/stats.json", json={
                    "threatsNeutralized": new_count,
                    "total_latency_ms": new_total_latency,
                    "avg_latency_ms": avg_latency,
                    "last_latency_ms": latency_ms,
                    "total_solved": new_total_solved
                })
                
                # Update active threat entry to "mitigated"
                if active_key:
                    action_msg = "Process SIGKILL & File Restored" if action_type == 0 else "System Throttled"
                    update_url = f"{FIREBASE_DB_URL}/active_threats/{active_key}.json"
                    requests.patch(update_url, json={
                        "action_taken": action_msg,
                        "status": "mitigated"
                    })
                    
                    # Schedule deletion
                    threading.Thread(target=delete_after_delay, args=(update_url,)).start()

                print(f"[*] Successfully processed threat mitigation for active_key: {active_key}")
            except Exception as e:
                print(f"[!] Failed to update Firebase UI: {e}")

            return jsonify({"status": "success", "action": "mlfq_handler_invoked"}), 200

        except Exception as e:
            print(f"[!] MLFQ Handler failed execution: {e}")
            return jsonify({"status": "error", "reason": "mlfq_handler_failed"}), 500
        
    return jsonify({"error": "No active Agent PID found."}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)
