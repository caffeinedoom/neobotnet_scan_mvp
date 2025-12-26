# ==============================================================================
# MULTI-STAGE DOCKERFILE FOR WAYMORE MODULE
# ==============================================================================
# Stage 1: Go builder - compiles the Go wrapper
# Stage 2: Python base - installs waymore and dependencies
# Stage 3: Runtime - combines Go binary with Python environment
# ==============================================================================

# ============================================================================
# STAGE 1: GO BUILDER
# ============================================================================
FROM golang:1.21-alpine AS go-builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache git ca-certificates

# Copy go mod files first for layer caching
COPY go.mod go.sum* ./

# Download dependencies
RUN go mod download

# Copy source code
COPY *.go ./

# Build the Go binary
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o waymore-scanner .

# ============================================================================
# STAGE 2: PYTHON BUILDER - Install waymore
# ============================================================================
FROM python:3.11-slim AS python-builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install waymore from PyPI (or from git for latest)
# Using pip with version pin for reproducibility
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir waymore

# ============================================================================
# STAGE 3: RUNTIME IMAGE
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python virtual environment from builder
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# FIX: Make waymore package directory writable for cache files (collinfo.json)
# Waymore needs to write to its package directory for CommonCrawl index
RUN chmod -R a+rw /opt/venv/lib/python3.11/site-packages/waymore/

# Copy Go binary from builder
COPY --from=go-builder /app/waymore-scanner /usr/local/bin/waymore-scanner

# Copy configuration file
COPY config.yml /app/config.yml

# Create temp directory for waymore output and cache
RUN mkdir -p /tmp/waymore /tmp/waymore-cache && chmod 777 /tmp/waymore /tmp/waymore-cache

# Create writable home directory for waymore/tldextract cache
RUN mkdir -p /app/.cache && chmod 777 /app/.cache
ENV HOME=/app

# Set environment defaults
ENV WAYMORE_CONFIG=/app/config.yml
ENV WAYMORE_LIMIT=5000
ENV WAYMORE_TIMEOUT=600

# Labels for container registry
LABEL maintainer="neobotnet"
LABEL module="waymore"
LABEL version="1.0"

# Health check - verify both Go and Python are working
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD waymore --version || exit 1

# Entry point is the Go binary which wraps waymore
ENTRYPOINT ["/usr/local/bin/waymore-scanner"]


