# Multi-stage production Dockerfile for TattvaSwarm Production Gateway
# Suitable for Google Cloud Run, Fly.io, or sovereign on-prem k8s

FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY meta_hackathon_2026/ ./meta_hackathon_2026/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ".[gateway]"

# Final runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Hardened unprivileged system user
RUN groupadd -g 10001 tattva && \
    useradd -u 10001 -g tattva -s /bin/bash -m tattva

# Copy installed packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/tattva /usr/local/bin/tattva
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy application files and runtime data directories
COPY --chown=tattva:tattva . /app

# Ensure directories for evidence and ledger are writable
RUN mkdir -p /app/data/evidence /app/frontier_eval/runs && \
    chown -R tattva:tattva /app/data /app/frontier_eval

USER tattva:tattva

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    X402_NETWORK=base-sepolia \
    EVIDENCE_DIR=/app/data/evidence

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

ENTRYPOINT ["tattva", "gateway", "serve", "--host", "0.0.0.0", "--port", "8080"]
