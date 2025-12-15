# ================================================================
# Enhanced Subfinder-Go Container for Web Reconnaissance Framework
# ================================================================
# This container performs multi-domain subdomain enumeration using 
# the subfinder SDK with Redis coordination for distributed processing
# 
# Phase 2 Enhancements:
# • Comprehensive health monitoring
# • Performance metrics collection
# • Enhanced observability
# • Better resource monitoring

FROM golang:1.24-alpine AS builder

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
COPY . .

# Build the application with optimizations
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -a -installsuffix cgo -o subfinder-go .

# Install subfinder binary for additional CLI functionality (if needed)
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

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
    htop \
    procps \
    util-linux

# Set working directory
WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/subfinder-go .

# Copy provider configuration file (REQUIRED even for free sources)
COPY --from=builder /app/provider-config.yaml /app/provider-config.yaml

# Copy subfinder binary from builder stage (for reference/debugging)
COPY --from=builder /go/bin/subfinder /usr/local/bin/subfinder

# Create enhanced health check script
RUN echo '#!/bin/bash' > /app/health-check.sh && \
    echo '# Enhanced health check for subfinder container' >> /app/health-check.sh && \
    echo 'if pgrep -f "subfinder-go" > /dev/null; then' >> /app/health-check.sh && \
    echo '  echo "✅ Process: Running"' >> /app/health-check.sh && \
    echo '  MEMORY_MB=$(awk "/MemAvailable/ {printf \"%.0f\", \$2/1024}" /proc/meminfo)' >> /app/health-check.sh && \
    echo '  echo "📊 Memory: ${MEMORY_MB}MB available"' >> /app/health-check.sh && \
    echo '  if [ -n "$REDIS_HOST" ]; then' >> /app/health-check.sh && \
    echo '    timeout 3 bash -c "</dev/tcp/$REDIS_HOST/${REDIS_PORT:-6379}" 2>/dev/null && echo "✅ Redis: Connected" || echo "⚠️ Redis: Disconnected"' >> /app/health-check.sh && \
    echo '  fi' >> /app/health-check.sh && \
    echo '  echo "✅ Overall: HEALTHY"' >> /app/health-check.sh && \
    echo '  exit 0' >> /app/health-check.sh && \
    echo 'else' >> /app/health-check.sh && \
    echo '  echo "❌ Process: Not running"' >> /app/health-check.sh && \
    echo '  exit 1' >> /app/health-check.sh && \
    echo 'fi' >> /app/health-check.sh && \
    chmod +x /app/health-check.sh

# Create performance monitoring script
RUN echo '#!/bin/bash' > /app/monitor.sh && \
    echo '# Performance monitoring for subfinder' >> /app/monitor.sh && \
    echo 'echo "{"' >> /app/monitor.sh && \
    echo 'echo "  \"timestamp\": \"$(date -Iseconds)\","' >> /app/monitor.sh && \
    echo 'echo "  \"memory_mb\": $(awk "/MemAvailable/ {printf \"%.0f\", \$2/1024}" /proc/meminfo),' >> /app/monitor.sh && \
    echo 'echo "  \"processes\": $(pgrep -c -f subfinder-go || echo 0),' >> /app/monitor.sh && \
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
      version="2.1.0" \
      description="Enhanced Subfinder-Go Scanner with comprehensive monitoring" \
      component="reconnaissance-scanner" \
      monitoring="enabled"

# Environment variables for configuration
ENV LOG_LEVEL=info \
    HEALTH_CHECK_ENABLED=true \
    METRICS_COLLECTION_ENABLED=true

# Default entrypoint
ENTRYPOINT ["./subfinder-go"]
