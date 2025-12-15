#!/bin/bash

# ================================================================
# Get Current ECS IP for Terraform Data Source
# Used by dns-fix.tf to manage DNS records in Terraform state
# ================================================================

set -e

# Parse input from Terraform
eval "$(jq -r '@sh "CLUSTER_NAME=\(.cluster_name) SERVICE_NAME=\(.service_name)"')"

# Get current task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --query 'taskArns[0]' \
  --output text 2>/dev/null || echo "None")

if [ "$TASK_ARN" = "None" ] || [ -z "$TASK_ARN" ]; then
    # No running task - return fallback IP
    jq -n --arg ip "127.0.0.1" '{"ip": $ip}'
    exit 0
fi

# Get ENI ID from task
ENI_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text 2>/dev/null || echo "")

if [ -z "$ENI_ID" ] || [ "$ENI_ID" = "None" ]; then
    # Can't get ENI - return fallback IP
    jq -n --arg ip "127.0.0.1" '{"ip": $ip}'
    exit 0
fi

# Get public IP from network interface
CURRENT_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text 2>/dev/null || echo "None")

if [ "$CURRENT_IP" = "None" ] || [ -z "$CURRENT_IP" ]; then
    # Can't get IP - return fallback
    jq -n --arg ip "127.0.0.1" '{"ip": $ip}'
    exit 0
fi

# Return the IP in JSON format for Terraform
jq -n --arg ip "$CURRENT_IP" '{"ip": $ip}'
