# Openbot Semantic Firewall

An OS-level security layer and telemetry pipeline designed to safely sandbox and monitor *any* autonomous AI agent, built for HackMerced.

## The Pitch
We didn't just fix or fork an existing AI codebase. Because our firewall wraps Operating System system calls via `LD_PRELOAD`, our software can protect against destructive actions from **any** autonomous AI agent on the market—OpenClaw, AutoGPT, Devin, etc.

## Architecture

1. **C/C++ Core Systems (Yash):** The `LD_PRELOAD` library hooks into `unlink`, `rm`, and `open` to instantly teleport files rather than delete them, operating in $O(1)$ time. 
2. **Telemetry Pipeline (Souradeep):** A Python wrapper streams all AI logs (stdout) over Wi-Fi directly to a Splunk Cloud index via HTTP Event Collectors.
3. **MLFQ Rules Engine (Souradeep):** Splunk SPL identifies malicious intent and bounces a Webhook back to our Edge Hardware.
4. **Kill Switch:** A local Flask server receives the webhook and triggers our C++ Dispatcher to execute a fast `kill -9` on the rogue AI.
5. **Real-time Dashboard (Harshith):** A React UI hooked into Firebase displays live intercept numbers and neutralized threats.

## How to Run

1. Clone this repository (which contains NO third-party AI code, making our codebase 100% pure).
2. Build the Edge Docker container (which will dynamically download OpenClaw to serve as the target test subject):
   ```bash
   docker-compose up --build
   ```
3. Watch the terminal as our C++ Hook intercepts AI anomalies!
4. Launch the dashboard:
   ```bash
   cd dashboard && npm run dev
   ```
