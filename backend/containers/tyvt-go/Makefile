# ============================================================
# TYVT Module - Makefile
# ============================================================

.PHONY: build run test clean docker-build docker-run

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOCLEAN=$(GOCMD) clean
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOMOD=$(GOCMD) mod

# Binary name
BINARY_NAME=tyvt-scanner

# Docker
DOCKER_IMAGE=tyvt-go:local
AWS_ACCOUNT_ID ?= 123456789
AWS_REGION ?= us-east-1
ECR_REPO=$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/neobotnet-v2-dev/tyvt

# Build the binary
build:
	$(GOBUILD) -o $(BINARY_NAME) -v .

# Run tests
test:
	$(GOTEST) -v ./...

# Download dependencies
deps:
	$(GOMOD) download
	$(GOMOD) tidy

# Clean build artifacts
clean:
	$(GOCLEAN)
	rm -f $(BINARY_NAME)

# Build Docker image
docker-build:
	docker build -t $(DOCKER_IMAGE) .

# Run in Docker (simple mode)
docker-run-simple:
	docker run --rm \
		-e SCAN_JOB_ID="test-$$(uuidgen)" \
		-e USER_ID="test-user" \
		-e ASSET_ID="test-asset" \
		-e SUBDOMAINS='["example.com"]' \
		-e SUPABASE_URL="$(SUPABASE_URL)" \
		-e SUPABASE_SERVICE_ROLE_KEY="$(SUPABASE_KEY)" \
		-e VT_API_KEYS="$(VT_API_KEYS)" \
		$(DOCKER_IMAGE)

# Run in Docker (streaming mode)
docker-run-streaming:
	docker run --rm \
		--network host \
		-e STREAMING_MODE=true \
		-e SCAN_JOB_ID="test-$$(uuidgen)" \
		-e USER_ID="test-user" \
		-e ASSET_ID="test-asset" \
		-e STREAM_INPUT_KEY="scan:test:httpx:output" \
		-e STREAM_OUTPUT_KEY="scan:test:tyvt:output" \
		-e CONSUMER_GROUP_NAME="tyvt-consumers" \
		-e CONSUMER_NAME="tyvt-task-1" \
		-e REDIS_HOST="localhost" \
		-e REDIS_PORT="6379" \
		-e SUPABASE_URL="$(SUPABASE_URL)" \
		-e SUPABASE_SERVICE_ROLE_KEY="$(SUPABASE_KEY)" \
		-e VT_API_KEYS="$(VT_API_KEYS)" \
		$(DOCKER_IMAGE)

# Push to ECR
docker-push:
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
	docker tag $(DOCKER_IMAGE) $(ECR_REPO):latest
	docker push $(ECR_REPO):latest

# All-in-one: build and push
deploy: docker-build docker-push
	@echo "✅ Deployed to ECR: $(ECR_REPO):latest"

