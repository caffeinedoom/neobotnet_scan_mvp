# ================================================================
# DNSX DNS Resolver Container for Web Reconnaissance Framework
# ================================================================
# This container performs DNS resolution for discovered subdomains using
# the dnsx library with batch processing support and database integration
#
# Features:
# • Multi-stage build for minimal image size
# • Comprehensive health monitoring
# • Non-root user for security
# • Enhanced observability
# • Resource monitoring

FROM golang:1.23-alpine AS builder

# Install system dependencies for building
RUN apk --no-cache add \
    git \
    ca-certificates \
    build-base \
    curl

# Set working directory
WORKDIR /app

# Copy go mod files first for better Docker layer caching
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY *.go ./

# Build the application with optimizations
# -ldflags="-w -s" strips debug info to reduce binary size
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -a -installsuffix cgo -o dnsx-scanner .

# Verify binary was created
RUN test -f /app/dnsx-scanner || (echo "Build failed: binary not found" && exit 1)

# ================================================================
# Production stage with enhanced monitoring
# ================================================================
FROM alpine:latest

# Install runtime dependencies including monitoring tools
RUN apk --no-cache add \
    ca-certificates \
    curl \
    bash \
    bind-tools \
    jq \
    procps \
    util-linux

# Set working directory
WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/dnsx-scanner .

# Verify binary is executable
RUN chmod +x /app/dnsx-scanner

# Create enhanced health check script
RUN echo '#!/bin/bash' > /app/health-check.sh && \
    echo '# Enhanced health check for DNSX container' >> /app/health-check.sh && \
    echo 'if pgrep -f "dnsx-scanner" > /dev/null; then' >> /app/health-check.sh && \
    echo '  echo "✅ Process: Running"' >> /app/health-check.sh && \
    echo '  MEMORY_MB=$(awk "/MemAvailable/ {printf \"%.0f\", \$2/1024}" /proc/meminfo)' >> /app/health-check.sh && \
    echo '  echo "📊 Memory: ${MEMORY_MB}MB available"' >> /app/health-check.sh && \
    echo '  echo "✅ Overall: HEALTHY"' >> /app/health-check.sh && \
    echo '  exit 0' >> /app/health-check.sh && \
    echo 'else' >> /app/health-check.sh && \
    echo '  echo "❌ Process: Not running"' >> /app/health-check.sh && \
    echo '  exit 1' >> /app/health-check.sh && \
    echo 'fi' >> /app/health-check.sh && \
    chmod +x /app/health-check.sh

# Create performance monitoring script
RUN echo '#!/bin/bash' > /app/monitor.sh && \
    echo '# Performance monitoring for DNSX' >> /app/monitor.sh && \
    echo 'echo "{"' >> /app/monitor.sh && \
    echo "  \"timestamp\": \"$(date -Iseconds)\"," >> /app/monitor.sh && \
    echo 'echo "  \"memory_mb\": $(awk "/MemAvailable/ {printf \"%.0f\", \$2/1024}" /proc/meminfo),' >> /app/monitor.sh && \
    echo 'echo "  \"processes\": $(pgrep -c -f dnsx-scanner || echo 0),' >> /app/monitor.sh && \
    echo 'echo "  \"uptime\": \"$(uptime -p)\"' >> /app/monitor.sh && \
    echo 'echo "}"' >> /app/monitor.sh && \
    chmod +x /app/monitor.sh

# Create non-root user for security
RUN addgroup -g 1001 scanner && \
    adduser -D -u 1001 -G scanner scanner && \
    chown -R scanner:scanner /app

# Switch to non-root user
USER scanner

# Enhanced health check with comprehensive monitoring
HEALTHCHECK --interval=30s --timeout=15s --start-period=10s --retries=3 \
    CMD /app/health-check.sh

# Add labels for better container management
LABEL maintainer="Pluckware Development Team" \
      version="1.0.0" \
      description="DNSX DNS Resolver with batch processing and database integration" \
      component="dns-resolver" \
      monitoring="enabled"

# Environment variables for configuration
ENV LOG_LEVEL=info \
    HEALTH_CHECK_ENABLED=true \
    METRICS_COLLECTION_ENABLED=true

# Default entrypoint
ENTRYPOINT ["./dnsx-scanner"]
