# Start with a lightweight Linux base image
FROM ubuntu:22.04

# Prevent interactive installer prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies: C++ compiler, Python, Node, Git, etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (OpenClaw requirement)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs

# Install Flask for the webhook server
RUN pip3 install Flask requests

# 1. Clone OpenClaw directly from the source (Not our repo!)
RUN git clone https://github.com/openclaw/openclaw.git /app/openclaw
RUN cd /app/openclaw && npm install -g pnpm && pnpm install && npm run build

# 2. Copy OUR custom security code into the container
COPY ./interceptor /app/interceptor
COPY ./telemetry /app/telemetry

# 3. Compile Yash's C++ Interceptor
RUN cd /app/interceptor && make

# 4. Set environment and command to run OpenClaw WRAPPED in our C++ interceptor and Python streamer
WORKDIR /app
CMD ["python3", "/app/telemetry/wrapper.py", "node", "/app/openclaw/dist/index.js", "gateway", "--port", "18789", "--allow-unconfigured"]
