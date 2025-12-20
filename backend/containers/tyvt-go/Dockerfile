# ============================================================
# TYVT - VirusTotal Domain Scanner Module
# NeoBot-Net v2 Scan Engine
# ============================================================
# Multi-stage build for minimal production image

# Stage 1: Build
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates

WORKDIR /app

# Copy go mod files first (for layer caching)
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build binary with optimizations
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -ldflags="-w -s -X main.Version=1.0.0" \
    -o tyvt-scanner .

# Stage 2: Runtime
FROM alpine:3.19

# Install runtime dependencies
RUN apk add --no-cache ca-certificates tzdata

# Create non-root user for security
RUN adduser -D -u 1000 scanner

# Set working directory
WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/tyvt-scanner .

# Change ownership
RUN chown -R scanner:scanner /app

# Switch to non-root user
USER scanner

# Health check endpoint (optional, for ECS health checks)
# HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
#     CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Entry point
ENTRYPOINT ["/app/tyvt-scanner"]

