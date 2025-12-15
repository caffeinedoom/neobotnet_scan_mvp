#!/bin/bash

# ================================================================
# ECS IP Update Script for Cost-Optimized Architecture
# Updates DNS record to point to current ECS task IP
# ================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
CLUSTER_NAME="neobotnet-v2-dev-cluster"
SERVICE_NAME="neobotnet-v2-dev-service"
HOSTED_ZONE_ID="Z057819416GVBBGQPEJPW"
ECS_DIRECT_DOMAIN="ecs-direct.aldous-api.neobotnet.com"
CLOUDFRONT_DISTRIBUTION_ID="E1BHLIL1N1MNB"
API_DOMAIN="aldous-api.neobotnet.com"
REGION="us-east-1"

echo -e "${BLUE}🔄 ECS IP Update Script${NC}"
echo -e "${BLUE}======================${NC}"

# ================================================================
# Step 1: Get Current ECS Task IP
# ================================================================
echo -e "\n${YELLOW}📋 Step 1: Getting Current ECS Task IP${NC}"

echo "🔍 Getting current ECS task..."
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --region "$REGION" \
  --query 'taskArns[0]' \
  --output text)

if [ "$TASK_ARN" == "None" ] || [ -z "$TASK_ARN" ]; then
    echo -e "${RED}❌ No running tasks found!${NC}"
    echo "Check if ECS service is running:"
    echo "  aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $REGION"
    exit 1
fi

echo "📋 Task ARN: ${TASK_ARN##*/}"

echo "🔌 Getting network interface..."
ENI_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --region "$REGION" \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text)

if [ -z "$ENI_ID" ] || [ "$ENI_ID" == "None" ]; then
    echo -e "${RED}❌ Could not get network interface ID!${NC}"
    exit 1
fi

echo "🔌 Network Interface: $ENI_ID"

echo "🌐 Getting public IP..."
CURRENT_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --region "$REGION" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text)

if [ "$CURRENT_IP" == "None" ] || [ -z "$CURRENT_IP" ]; then
    echo -e "${RED}❌ Could not get public IP!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Current ECS Task IP: $CURRENT_IP${NC}"

# ================================================================
# Step 2: Check Current DNS Record
# ================================================================
echo -e "\n${YELLOW}📋 Step 2: Checking Current DNS Record${NC}"

DNS_IP=$(dig +short "$ECS_DIRECT_DOMAIN" | head -1)
echo "🔗 DNS Currently Points to: $DNS_IP"

if [ "$CURRENT_IP" = "$DNS_IP" ]; then
    echo -e "${GREEN}✅ DNS already points to current ECS task!${NC}"
    SKIP_DNS_UPDATE=true
else
    echo -e "${YELLOW}⚠️ DNS needs update: $DNS_IP → $CURRENT_IP${NC}"
    SKIP_DNS_UPDATE=false
fi

# ================================================================
# Step 3: Test Current Backend Health
# ================================================================
echo -e "\n${YELLOW}📋 Step 3: Testing Backend Health${NC}"

echo "🩺 Testing direct backend access..."
if curl -f --max-time 10 "http://$CURRENT_IP:8000/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend is healthy on $CURRENT_IP:8000${NC}"
else
    echo -e "${RED}❌ Backend not responding on $CURRENT_IP:8000${NC}"
    echo "This could indicate a backend issue. Continuing with DNS update..."
fi

# ================================================================
# Step 4: Update DNS Record (if needed)
# ================================================================
if [ "$SKIP_DNS_UPDATE" = false ]; then
    echo -e "\n${YELLOW}📋 Step 4: Updating DNS Record${NC}"
    
    echo "🔄 Updating DNS record: $DNS_IP → $CURRENT_IP"
    
    CHANGE_ID=$(aws route53 change-resource-record-sets \
      --hosted-zone-id "$HOSTED_ZONE_ID" \
      --change-batch "{
        \"Changes\": [{
          \"Action\": \"UPSERT\",
          \"ResourceRecordSet\": {
            \"Name\": \"$ECS_DIRECT_DOMAIN\",
            \"Type\": \"A\",
            \"TTL\": 60,
            \"ResourceRecords\": [{\"Value\": \"$CURRENT_IP\"}]
          }
        }]
      }" \
      --query 'ChangeInfo.Id' \
      --output text)
    
    echo "📝 Route53 Change ID: $CHANGE_ID"
    echo "⏳ Waiting for DNS propagation (30 seconds)..."
    sleep 30
    
    # Verify DNS update
    NEW_DNS_IP=$(dig +short "$ECS_DIRECT_DOMAIN" | head -1)
    if [ "$NEW_DNS_IP" = "$CURRENT_IP" ]; then
        echo -e "${GREEN}✅ DNS update successful!${NC}"
    else
        echo -e "${YELLOW}⚠️ DNS propagation may take longer. Current: $NEW_DNS_IP${NC}"
    fi
else
    echo -e "\n${GREEN}✅ Step 4: DNS Update Skipped (already correct)${NC}"
fi

# ================================================================
# Step 5: Clear CloudFront Cache (Optional)
# ================================================================
echo -e "\n${YELLOW}📋 Step 5: CloudFront Cache Management${NC}"

if [ "$SKIP_DNS_UPDATE" = false ]; then
    echo "🔄 Creating CloudFront cache invalidation..."
    
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
      --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" \
      --paths "/*" \
      --query 'Invalidation.Id' \
      --output text)
    
    echo "📝 CloudFront Invalidation ID: $INVALIDATION_ID"
    echo "⏳ Cache invalidation started (will take 3-5 minutes to complete)"
else
    echo "⏭️ Skipping CloudFront invalidation (DNS unchanged)"
fi

# ================================================================
# Step 6: Final Health Checks
# ================================================================
echo -e "\n${YELLOW}📋 Step 6: Final Health Checks${NC}"

echo "🔍 Testing direct backend access..."
if curl -f --max-time 10 "http://$CURRENT_IP:8000/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Direct backend: http://$CURRENT_IP:8000/health${NC}"
else
    echo -e "${RED}❌ Direct backend: http://$CURRENT_IP:8000/health${NC}"
fi

echo "🔍 Testing CloudFront endpoint..."
if curl -f --max-time 10 "https://$API_DOMAIN/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ CloudFront: https://$API_DOMAIN/health${NC}"
else
    echo -e "${YELLOW}⚠️ CloudFront: https://$API_DOMAIN/health (may need cache invalidation time)${NC}"
fi

# ================================================================
# Summary
# ================================================================
echo ""
echo -e "${GREEN}🎯 UPDATE COMPLETED!${NC}"
echo ""
echo "📊 Summary:"
echo "  ├── ECS Task IP: $CURRENT_IP"
echo "  ├── DNS Record: $ECS_DIRECT_DOMAIN → $CURRENT_IP"
echo "  ├── Direct API: http://$CURRENT_IP:8000"
echo "  └── HTTPS API: https://$API_DOMAIN"
echo ""
echo "🔍 Verification commands:"
echo "  ├── curl http://$CURRENT_IP:8000/health"
echo "  ├── curl https://$API_DOMAIN/health"
echo "  └── dig +short $ECS_DIRECT_DOMAIN"
echo ""

if [ "$SKIP_DNS_UPDATE" = false ]; then
    echo -e "${BLUE}💡 CloudFront cache invalidation is in progress${NC}"
    echo "    It may take 3-5 minutes for changes to be fully propagated."
    echo ""
    echo "    Monitor invalidation status:"
    echo "    aws cloudfront get-invalidation --distribution-id $CLOUDFRONT_DISTRIBUTION_ID --id $INVALIDATION_ID"
fi

echo -e "${BLUE}💡 This script can be run anytime your ECS task IP changes!${NC}"
