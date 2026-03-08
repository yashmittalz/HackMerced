#!/usr/bin/env python3
import subprocess
import time
import json
import urllib.request
import urllib.error
import sys
import os

def run_command(cmd, shell=False):
    """Run a shell command and stream output"""
    print(f"\n[>] Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        subprocess.run(cmd, shell=shell, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Command failed: {e}")
        sys.exit(1)

def kill_existing_ngrok():
    """Kill any actively running ngrok processes"""
    print("\n[*] Checking for existing Ngrok processes to kill...")
    try:
        if os.name == 'nt':
            subprocess.run(["taskkill", "/f", "/im", "ngrok.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "ngrok"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1) # Give OS a moment to release the port
    except Exception:
        pass

def start_ngrok():
    """Start ngrok in the background and extract the randomized URL"""
    print("\n[?] Starting ngrok on port 5005...")
    
    # We must start ngrok, but normally it blocks the terminal with a UI.
    # We can pipe it or run standard output natively to capture the log format it initializes with.
    try:
        # Popen ngrok
        ngrok_cmd = ["ngrok", "http", "5005", "--log=stdout"]
        process = subprocess.Popen(
            ngrok_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            shell=os.name == 'nt'
        )
        
        url = None
        # Scrape the logs until we see the "obj=tunnels name=command_line url=..." line
        print("    Waiting for ngrok to assign a public URL...")
        start_time = time.time()
        
        if process.stdout:
            while time.time() - start_time < 10:
                line = process.stdout.readline()
                if not line:
                    continue
                    
                if "url=https://" in line:
                    # Extract the URL section
                    parts = line.split()
                    for part in parts:
                        if part.startswith("url="):
                            url = part.split("=")[1]
                            break
                    
                if url:
                    break
                
        if not url:
            print("[!] Error: Ngrok did not assign a URL in time. Output:")
            if process.stderr:
                print(process.stderr.read())
            process.kill()
            return None, None
            
        print(f"    Assigned URL: {url}")
        return url, process
        
    except FileNotFoundError:
        print("[!] Error: ngrok executable not found in PATH.")
        return None, None

def main():
    print("==================================================")
    print("   Semantic Firewall - E2E Integration Tester   ")
    print("==================================================")

    # 1. Restart Docker Containers
    print("\n[*] Step 1: Rebuilding & Restarting Docker Containers...")
    is_windows = os.name == 'nt'
    
    # Use 'docker compose' (v2) which is standard now
    compose_cmd = ["docker", "compose", "up", "-d", "--build"]
    run_command(compose_cmd, shell=is_windows)

    # Give the container a few seconds to boot the Flask server
    print("\n[*] Waiting 5 seconds for Webhook Server to boot...")
    time.sleep(5)

    # 2. Start Ngrok Background Process
    print("\n[*] Step 2: Bootstrapping Ngrok Tunnel...")
    kill_existing_ngrok()
    ngrok_url, ngrok_proc = start_ngrok()
    
    if not ngrok_url:
        print("[!] Check if ngrok is authenticated or currently running elsewhere.")
        sys.exit(1)
        
    webhook_endpoint = f"{ngrok_url}/splunk-alert"
    print(f"[+] Webhook Endpoint: {webhook_endpoint}")
    
    # Wait for the tunnel to establish upstream connection to localhost:5005
    time.sleep(3)

    # 3. Fire Test Webhook
    print("\n[*] Step 3: Simulating Splunk Alert via Ngrok...")
    payload = {
        "source": "E2E_Test_Script",
        "description": "Simulated Splunk Threat Detection",
        "pid": "1234" # Dummy PID for testing
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        webhook_endpoint, 
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        print(f"[*] Sending POST Request to {webhook_endpoint}...")
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            response_body = response.read().decode('utf-8')
            print(f"[+] Success! Server responded with HTTP {status}")
            print(f"    Response Body: {response_body}")
            print("\n[✓] END-TO-END TEST PASSED! The pipeline is fully functional.")
            
    except urllib.error.HTTPError as e:
        print(f"[!] HTTP Error {e.code}: {e.reason}")
        print(f"    Response Body: {e.read().decode('utf-8')}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[!] Connection Error: {e.reason}")
    
    finally:
        # Cleanup ngrok process at the end
        if 'ngrok_proc' in locals() and ngrok_proc:
            print("\n[*] Tearing down ngrok tunnel...")
            ngrok_proc.kill()

if __name__ == "__main__":
    main()
