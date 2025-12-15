#!/bin/bash

# ================================================================
# Quick ECS Task IP Lookup
# Utility script for debugging and manual DNS updates
# ================================================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
CLUSTER_NAME="neobotnet-v2-dev-cluster"
SERVICE_NAME="neobotnet-v2-dev-service"
ECS_DIRECT_DOMAIN="ecs-direct.aldous-api.neobotnet.com"

echo -e "${BLUE}🔍 Getting Current ECS Task Information${NC}"

# Get current task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --query 'taskArns[0]' \
  --output text)

if [ "$TASK_ARN" == "None" ] || [ -z "$TASK_ARN" ]; then
    echo "❌ No running tasks found!"
    echo "Check if ECS service is running: aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME"
    exit 1
fi

# Get ENI ID
ENI_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text)

# Get public IP
CURRENT_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text)

# Get DNS IP for comparison
DNS_IP=$(dig +short "$ECS_DIRECT_DOMAIN" | head -1)

echo ""
echo -e "${GREEN}📋 Current ECS Task Information:${NC}"
echo "  Task ARN: ${TASK_ARN##*/}"  # Show just the task ID part
echo "  ENI ID: $ENI_ID"
echo "  Current IP: $CURRENT_IP"
echo "  DNS Points to: $DNS_IP"

if [ "$CURRENT_IP" = "$DNS_IP" ]; then
    echo -e "  Status: ${GREEN}✅ DNS is correct${NC}"
else
    echo -e "  Status: ⚠️  DNS needs update"
    echo ""
    echo "To update DNS manually:"
    echo "  aws route53 change-resource-record-sets --hosted-zone-id Z057819416GVBBGQPEJPW --change-batch '{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"$ECS_DIRECT_DOMAIN\",\"Type\":\"A\",\"TTL\":60,\"ResourceRecords\":[{\"Value\":\"$CURRENT_IP\"}]}}]}'"
fi

echo ""
echo "🔍 Quick tests:"
echo "  Direct: curl http://$CURRENT_IP:8000/health"
echo "  HTTPS: curl https://aldous-api.neobotnet.com/health"
