#!/usr/bin/env python3
from flask import Flask, request, jsonify
import requests
import json
import os
import time

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except ImportError:
    print("[!] vaderSentiment not installed. Please run: pip install vaderSentiment")
    import sys
    sys.exit(1)

app = Flask(__name__)
analyzer = SentimentIntensityAnalyzer()

# Where to send the assigned priority 
WEBHOOK_URL = "http://localhost:5005/splunk-alert"
FIREBASE_DB_URL = os.environ.get("FIREBASE_DATABASE_URL", "https://openclaw-sentinal-default-rtdb.firebaseio.com")

def calculate_mlfq_priority(log_text):
    """
    Analyzes the semantic threat level of a log and assigns an MLFQ Priority Queue.
     Priority 0: Extremely Malicious (Immediate Kill & Rollback) [ActionType 0]
    Priority 1: Suspicious (Throttle / Sandbox) [ActionType 2]
    Priority 2: Monitor (Normal Queue) [ActionType 3]
    Priority 3: Safe (Background Queue) [No Action]
    Returns: (mlfq_priority, action_type, compound_score)
    """
    # ─── OpenClaw Internal Subsystem Whitelist ───────────────────────────────
    # Known internal OpenClaw systems & false positive patterns
    whitelisted_patterns = [
        # OpenClaw specifics
        "[gateway]", "[browser/server]", "[canvas]", "[heartbeat]",
        "[health-monitor]", "control ui", "os interceptor loaded",
        "[security firewall]", "agent model", "listening on ws",
        "log file", "auth mode", "security warning",
        "chrome extension relay init failed", "browser control listening",
        "openclaw is ready", "[ws]", "[diagnostic]", "model context window",
        "embedded agent failed",
        
        # Node.js and Package Manager noise
        "deprecationwarning", "trace-deprecation", "the warning was created",
        "(node:", "npm info", "npm warn", "experimental warning",
        "npm err!", "webpack compiled", "vite v", "ready in",
        "local:   http", "network: use --host", "press h to show help",
        
        # Docker and generic system startup noise
        "starting", "waiting for", "online", "serving flask app",
        "debug mode: off", "warning: this is a development server",
        "running on", "press ctrl+c to quit", "is up on port",
        "skipping onboarding", "handing off to", "all stdout is being intercepted"
    ]
    lower_text = log_text.lower()
    for safe_pattern in whitelisted_patterns:
        if safe_pattern in lower_text:
            return 3, -1, 1.0  # Whitelisted internal log — never alert, safe compound

    # Force certain keywords to trigger hardcoded malicious analysis for demo
    if "malicious" in lower_text or "rogue" in lower_text:
        return 0, 0, -1.0
        
    # Run the VADER NLP Sentiment Analyzer on the raw text
    # The compound score is bounded between -1 (extreme negative) and +1 (extreme positive)
    sentiment = analyzer.polarity_scores(log_text)
    compound = sentiment['compound']
    
    # Map the sentiment distribution to MLFQ Priority Queues and Dispatch Actions
    if compound <= -0.5:
        # Heavily negative semantics — treat as critical threat
        return 0, 0, compound # Priority 0, Action 0 (Neutralize)
    elif -0.5 < compound <= -0.1:
        # Mildly negative semantics — suspicious
        return 1, 2, compound # Priority 1, Action 2 (Throttle)
    else:
        # Neutral or positive — safe, no action taken
        return 3, -1, compound # Safe, no action

# Startup grace: don't attempt Firebase for the first 5 seconds while Docker DNS initializes
last_firebase_update = time.time() + 5

def update_firebase_hostility(compound_score):
    """Converts the VADER compound score (-1.0 to 1.0) to a hostility index 0 to 100"""
    global last_firebase_update
    
    # Skip entirely for safe/whitelisted logs (compound == 1.0 means hostility_index == 0)
    if compound_score == 1.0:
        return
    
    try:
        # -1.0 becomes 100, 1.0 becomes 0
        hostility_index = int(((-compound_score + 1) / 2) * 100)
        
        current_time = time.time()
        # Rate limit: update at most once per second, BUT bypass immediately on high threats
        is_threat = hostility_index > 50
        cooldown_elapsed = (current_time - last_firebase_update) > 1.0
        
        if is_threat or cooldown_elapsed:
            requests.patch(f"{FIREBASE_DB_URL}/stats.json", json={"hostility_index": hostility_index}, timeout=3)
            last_firebase_update = current_time
    except requests.exceptions.ConnectionError:
        print(f"[!] Docker DNS Warning: Firebase unreachable, will retry on next log.")
    except requests.exceptions.Timeout:
        print(f"[!] Firebase Timeout: Skipping this update.")
    except Exception as e:
        print(f"[!] General Firebase error: {e}")

def post_threat_to_firebase(log_message, mlfq_priority, action_type, pid):
    """
    Writes a properly structured threat record to Firebase for the App.jsx dashboard.
    Writes to both threat_history (persistent) and active_threats (live ticker).
    """
    try:
        threat_level = "CRITICAL" if mlfq_priority == 0 else "HIGH"
        action_map = {0: "Process SIGKILL & File Restored", 1: "System Rollback Triggered", 2: "Network Throttled", 3: "Violation Logged"}
        action_taken = action_map.get(action_type, "NLP Flag")
        
        # Truncate message for display — long log lines are noisy in the UI
        display_message = (log_message[:120] + "...") if len(log_message) > 120 else log_message
        
        threat_record = {
            "pid_killed": pid,
            "threat_level": threat_level,
            "action_taken": action_taken,
            "agent_thought": display_message,
            "vector": "NLP Semantic Analysis",
            "timestamp": time.time(),
            "status": "active",
            "mlfq_priority": mlfq_priority
        }
        
        # 1. Write to persistent threat history
        requests.post(f"{FIREBASE_DB_URL}/threat_history.json", json=threat_record, timeout=3)
        
        # 2. Write to active threats (live dashboard ticker)
        resp = requests.post(f"{FIREBASE_DB_URL}/active_threats.json", json=threat_record, timeout=3)
        active_key = resp.json().get('name') if resp.ok else None
        
        # 3. Increment threat counter in stats
        resp = requests.get(f"{FIREBASE_DB_URL}/stats/threatsNeutralized.json", timeout=2)
        current = resp.json() if resp.ok and resp.text != 'null' else 0
        requests.patch(f"{FIREBASE_DB_URL}/stats.json", json={
            "threatsNeutralized": (current or 0) + 1,
            "total_received": (current or 0) + 1
        }, timeout=2)
        
        # 4. Auto-delete from active_threats after 5 seconds (like webhook_server does)
        if active_key:
            def _cleanup():
                import time as _time; _time.sleep(5)
                try:
                    requests.delete(f"{FIREBASE_DB_URL}/active_threats/{active_key}.json", timeout=2)
                except Exception:
                    pass
            import threading
            threading.Thread(target=_cleanup, daemon=True).start()
            
    except requests.exceptions.ConnectionError:
        print(f"[!] Firebase Threat Post: DNS failure, skipping.")
    except Exception as e:
        print(f"[!] Failed to post threat to Firebase: {e}")

@app.route('/analyze', methods=['POST'])
def analyze_log():
    data = request.json
    if not data or 'event' not in data:
        return jsonify({"error": "Invalid log format"}), 400
        
    event_data = data['event']
    log_message = event_data.get('message', "")
    
    print(f"\n[AI] Analyzing Telemetry: {log_message}")
    
    # 1. Classify the threat level using NLP
    mlfq_priority, action_type, compound_score = calculate_mlfq_priority(log_message)
    print(f"[AI] Assigned MLFQ Priority: {mlfq_priority}, ActionType: {action_type}")
    
    # Update Firebase UI stats with calculated index
    update_firebase_hostility(compound_score)
    
    # 2. If it is suspicious/malicious (-1 means safe), forward it to the C++ Handler Webhook
    if action_type != -1:
        print(f"[!] Threat Detected! Forwarding PID to MLFQ Webhook Server... (Priority {mlfq_priority})")
        
        target_pid = event_data.get('pid', '1234')
        
        # Post a structured threat record to Firebase for the dashboard
        post_threat_to_firebase(log_message, mlfq_priority, action_type, target_pid)
        
        payload = {
            "source": "Local_ML_Analyzer",
            "description": log_message,
            "pid": target_pid,
            "mlfq_priority": mlfq_priority,
            "action_type": action_type
        }
        
        try:
            requests.post(WEBHOOK_URL, json=payload, timeout=2)
            print("[+] Successfully triggered C++ MLFQ Hook!")
        except Exception as e:
            print(f"[!] Failed to reach local webhook: {e}")
            
    return jsonify({
        "status": "analyzed", 
        "priority": mlfq_priority,
        "action_taken": "mitigated" if mlfq_priority <= 1 else "none"
    }), 200

if __name__ == '__main__':
    print("[*] Local ML Threat Analyzer Online (Port 5006)")
    # Must bind to 0.0.0.0 so Docker can expose it to the host machine
    app.run(host='0.0.0.0', port=5006)