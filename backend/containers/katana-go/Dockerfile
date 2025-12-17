# ================================================================
# Katana Test Container - Minimal Crawler for Output Analysis
# ================================================================
# Purpose: Test Katana library integration and analyze output structure
# before implementing full production module
#
# Critical Requirements:
# • Chromium for headless mode
# • Non-root user (Chrome security requirement)
# • Proper output directory permissions
# ================================================================

# ================================================================
# Stage 1: Builder
# ================================================================
FROM golang:1.23-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    git \
    ca-certificates \
    build-base \
    curl

# Set working directory
WORKDIR /app

# Copy go.mod and go.sum for better Docker layer caching
COPY go.mod go.sum ./

# Download dependencies (GOTOOLCHAIN=auto allows automatic Go version download)
ENV GOTOOLCHAIN=auto
RUN go mod download

# Copy source code (including internal packages)
COPY main.go ./
COPY internal/ ./internal/

# Build the application with CGO enabled (required for Katana's JavaScript parsing)
# Katana uses tree-sitter which requires C bindings
RUN CGO_ENABLED=1 GOOS=linux go build -ldflags="-w -s" -o katana-go .

# Verify binary was created successfully
RUN test -f /app/katana-go || (echo "❌ Build failed: binary not found" && exit 1)

# ================================================================
# Stage 2: Production (with Chromium)
# ================================================================
FROM alpine:latest

# Install runtime dependencies including Chromium
# Critical: chromium is required for headless mode
RUN apk add --no-cache \
    ca-certificates \
    chromium \
    chromium-chromedriver \
    bash \
    curl \
    jq

# Create non-root user for Chrome execution
# Chrome refuses to run as root for security reasons
RUN addgroup -g 1001 katana && \
    adduser -D -u 1001 -G katana katana

# Set working directory
WORKDIR /app

# Create output directory with proper permissions
# This will be mounted as a volume for result collection
RUN mkdir -p /app/output && \
    chown -R katana:katana /app

# Copy binary from builder stage
COPY --from=builder /app/katana-go .

# Ensure binary is executable
RUN chmod +x /app/katana-go

# Switch to non-root user (CRITICAL for headless Chrome)
# This must be done BEFORE the ENTRYPOINT
USER katana

# Set environment variables for Chromium
# Katana library uses these to locate Chrome binary
ENV CHROME_BIN=/usr/bin/chromium-browser \
    CHROME_PATH=/usr/bin/chromium-browser \
    CHROMIUM_PATH=/usr/bin/chromium-browser

# Add labels for container management
LABEL maintainer="Pluckware Development Team" \
      version="1.0.0" \
      description="Katana Web Crawler Module for NeoBot-Net v2" \
      component="scanner" \
      module.name="katana-go" \
      module.type="consumer"

# Default entrypoint
ENTRYPOINT ["./katana-go"]
