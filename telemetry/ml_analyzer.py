#!/usr/bin/env python3
from flask import Flask, request, jsonify
import requests
import json
import os

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

def calculate_mlfq_priority(log_text):
    """
    Analyzes the semantic threat level of a log and assigns an MLFQ Priority Queue.
    Priority 0: Extremely Malicious (Immediate Kill & Rollback) [ActionType 0]
    Priority 1: Suspicious (Throttle / Sandbox) [ActionType 2]
    Priority 2: Monitor (Normal Queue) [ActionType 3]
    Priority 3: Safe (Background Queue) [No Action]
    """
    # ─── OpenClaw Internal Subsystem Whitelist ───────────────────────────────
    # Known internal OpenClaw systems & false positive patterns
    whitelisted_patterns = [
        "[gateway]", "[browser/server]", "[canvas]", "[heartbeat]",
        "[health-monitor]", "control ui", "deprecationwarning",
        "OS Interceptor loaded", "[SECURITY FIREWALL]", "agent model",
        "listening on ws", "log file", "auth mode", "security warning",
        "Chrome extension relay init failed", "Browser control listening",
        "OpenClaw is READY", "[ws]", "[diagnostic]", "Model context window",
        "Embedded agent failed"
    ]
    lower_text = log_text.lower()
    for safe_pattern in whitelisted_patterns:
        if safe_pattern in lower_text:
            return 3, -1  # Whitelisted internal log — never alert

    # Force certain keywords to trigger hardcoded malicious analysis for demo
    if "malicious" in lower_text or "rogue" in lower_text:
        return 0, 0
        
    # Run the VADER NLP Sentiment Analyzer on the raw text
    # The compound score is bounded between -1 (extreme negative) and +1 (extreme positive)
    sentiment = analyzer.polarity_scores(log_text)
    compound = sentiment['compound']
    
    # Map the sentiment distribution to MLFQ Priority Queues and Dispatch Actions
    if compound <= -0.5:
        # Heavily negative semantics — treat as critical threat
        return 0, 0 # Priority 0, Action 0 (Neutralize)
    elif -0.5 < compound <= -0.1:
        # Mildly negative semantics — suspicious
        return 1, 2 # Priority 1, Action 2 (Throttle)
    else:
        # Neutral or positive — safe, no action taken
        return 3, -1 # Safe, no action

@app.route('/analyze', methods=['POST'])
def analyze_log():
    data = request.json
    if not data or 'event' not in data:
        return jsonify({"error": "Invalid log format"}), 400
        
    event_data = data['event']
    log_message = event_data.get('message', "")
    
    print(f"\n[AI] Analyzing Telemetry: {log_message}")
    
    # 1. Classify the threat level using NLP
    mlfq_priority, action_type = calculate_mlfq_priority(log_message)
    print(f"[AI] Assigned MLFQ Priority: {mlfq_priority}, ActionType: {action_type}")
    
    # 2. If it is suspicious/malicious (-1 means safe), forward it to the C++ Handler Webhook
    if action_type != -1:
        print(f"[!] Threat Detected! Forwarding PID to MLFQ Webhook Server... (Priority {mlfq_priority})")
        
        # We assume the wrapper embedded the PID of the process in the message, 
        # or the wrapper itself sends it alongside the message.
        # For this architecture, we tell the webhook the PID (falling back to a dummy if missing)
        target_pid = event_data.get('pid', '1234')
        
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