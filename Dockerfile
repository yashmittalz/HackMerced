# Start with a lightweight Linux base image
FROM ubuntu:22.04

# Prevent interactive installer prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies: C++ compiler, Python, Node, Git, curl
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js v22 — OpenClaw hard-requires >=22.12.0 at runtime
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs

# Install Python deps for the ML Analyzer and Webhook Server
RUN pip3 install Flask requests vaderSentiment

# 1. Clone and build OpenClaw from source
RUN git clone https://github.com/openclaw/openclaw.git /app/openclaw
RUN cd /app/openclaw && npm install -g pnpm && pnpm install && npm run build

# 2. Copy OUR custom security layer into the container
COPY ./interceptor /app/interceptor
COPY ./telemetry /app/telemetry

# 3. Compile the C++ interceptor (produces hook.so and mlfq_handler)
RUN cd /app/interceptor && make

# 4. Copy and register the startup orchestration entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

WORKDIR /app

# entrypoint.sh handles ordered startup:
#   1. ML Analyzer (:5006) + health check
#   2. Webhook Server (:5005) + health check
#   3. First-run detection → OpenClaw onboarding or direct boot
ENTRYPOINT ["/app/entrypoint.sh"]
