# URL Resolver Container
# Resolves discovered URLs and stores enriched metadata

FROM golang:1.24-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git ca-certificates

# Set working directory
WORKDIR /app

# Copy go mod files
COPY go.mod go.sum* ./

# Download dependencies
RUN go mod download

# Copy source code
COPY *.go ./

# Build the binary
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o url-resolver .

# ============================================================
# Runtime stage
# ============================================================
FROM alpine:3.19

# Install runtime dependencies
RUN apk add --no-cache ca-certificates tzdata

# Create non-root user
RUN adduser -D -u 1000 resolver

# Set working directory
WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/url-resolver .

# Set ownership
RUN chown -R resolver:resolver /app

# Switch to non-root user
USER resolver

# Set default environment variables
ENV STREAMING_MODE=true
ENV BATCH_SIZE=10
ENV BLOCK_MILLISECONDS=5000
# Container timeout matches orchestrator pipeline timeout (3 hours)
ENV MAX_PROCESSING_TIME=10800
ENV RESOLUTION_TTL_HOURS=24
ENV PROBE_BATCH_SIZE=100

# Run the resolver
ENTRYPOINT ["./url-resolver"]

