# NeoBot-Net Scan Orchestrator
# Runs scan_pipeline.py inside AWS VPC with Redis access
#
# Build: docker build -t neobotnet-orchestrator .
# Run: (via ECS task with environment variables)

# Use existing backend as base (has all dependencies)
ARG ECR_REGISTRY
FROM ${ECR_REGISTRY}/neobotnet-backend:latest

# Set working directory
WORKDIR /app

# Copy orchestrator script
COPY main.py /app/orchestrator/main.py

# Set Python path to include backend
ENV PYTHONPATH=/app

# Default entrypoint runs the orchestrator
ENTRYPOINT ["python", "/app/orchestrator/main.py"]

