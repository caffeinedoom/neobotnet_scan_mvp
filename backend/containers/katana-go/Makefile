.PHONY: help test test-verbose test-coverage test-bench build clean lint fmt

# Default target
help:
	@echo "Katana Module - Make Commands"
	@echo "=============================="
	@echo "make test          - Run all tests"
	@echo "make test-verbose  - Run tests with verbose output"
	@echo "make test-coverage - Run tests with coverage report"
	@echo "make test-bench    - Run benchmarks"
	@echo "make build         - Build the binary"
	@echo "make clean         - Clean build artifacts"
	@echo "make lint          - Run linter (golangci-lint)"
	@echo "make fmt           - Format code"

# Run all tests
test:
	@echo "Running all tests..."
	@go test ./internal/...

# Run tests with verbose output
test-verbose:
	@echo "Running tests (verbose)..."
	@go test -v ./internal/...

# Run tests with coverage
test-coverage:
	@echo "Running tests with coverage..."
	@go test -cover ./internal/...
	@echo ""
	@echo "Generating HTML coverage report..."
	@go test -coverprofile=coverage.out ./internal/...
	@go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report saved to coverage.html"

# Run benchmarks
test-bench:
	@echo "Running benchmarks..."
	@go test -bench=. -benchmem ./internal/dedup/

# Build the binary
build:
	@echo "Building katana-go..."
	@go build -o bin/katana-go main.go
	@echo "Binary built: bin/katana-go"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -f bin/katana-go coverage.out coverage.html
	@echo "Clean complete"

# Run linter (requires golangci-lint)
lint:
	@echo "Running linter..."
	@golangci-lint run || echo "Note: Install golangci-lint to use this target"

# Format code
fmt:
	@echo "Formatting code..."
	@go fmt ./...
	@echo "Format complete"

# Run tests with race detector
test-race:
	@echo "Running tests with race detector..."
	@go test -race ./internal/...

# Run specific test
test-dedup:
	@go test -v ./internal/dedup/

test-config:
	@go test -v ./internal/config/

# Docker build
docker-build:
	@echo "Building Docker image..."
	@docker build -t katana-go:latest .

# Docker run (simple mode example)
docker-run:
	@echo "Running Docker container (requires env vars)..."
	@docker run --rm \
		-e SCAN_JOB_ID="test-job" \
		-e ASSET_ID="test-asset" \
		-e USER_ID="test-user" \
		-e SUPABASE_URL="${SUPABASE_URL}" \
		-e SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY}" \
		-e TARGET_URLS="https://example.com" \
		katana-go:latest

