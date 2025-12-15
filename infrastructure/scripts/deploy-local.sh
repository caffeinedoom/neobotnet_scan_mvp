#!/bin/bash

# ================================================================
# Unified Local Deployment Script
# Mirrors GitHub Actions workflow for consistency
# ================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="neobotnet-v2-dev-cluster"
SERVICE_NAME="neobotnet-v2-dev-service"
HOSTED_ZONE_ID="Z057819416GVBBGQPEJPW"
ECS_DIRECT_DOMAIN="ecs-direct.aldous-api.neobotnet.com"

echo -e "${BLUE}🚀 Starting Unified Local Deployment${NC}"

# ================================================================
# Step 1: Validate Environment
# ================================================================
echo -e "${YELLOW}📋 Step 1: Validating Environment${NC}"

# Check if terraform.tfvars exists with real values
if [ ! -f "terraform.tfvars" ]; then
    echo -e "${RED}❌ terraform.tfvars not found!${NC}"
    echo "Please copy terraform.tfvars.example to terraform.tfvars and fill in your actual secrets"
    exit 1
fi

# Check for placeholder values
if grep -q "your-supabase-anon-key\|your-supabase-service-role-key\|your-super-secret-jwt-key" terraform.tfvars; then
    echo -e "${RED}❌ Placeholder values found in terraform.tfvars!${NC}"
    echo "Please replace all placeholder values with your actual secrets"
    exit 1
fi

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found! Please install and configure AWS CLI${NC}"
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment validation passed${NC}"

# ================================================================
# Step 2: Terraform Deployment
# ================================================================
echo -e "${YELLOW}📋 Step 2: Terraform Deployment${NC}"

echo "🔄 Initializing Terraform..."
terraform init

echo "🔍 Planning Terraform changes..."
terraform plan -out=tfplan

echo "🚀 Applying Terraform changes..."
terraform apply tfplan

# Get current ECS IP for DNS update
echo "🔍 Getting current ECS task IP..."
CURRENT_IP=""
if aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" --query 'services[0].runningCount' --output text | grep -q "1"; then
    TASK_ARN=$(aws ecs list-tasks --cluster "$CLUSTER_NAME" --service-name "$SERVICE_NAME" --query 'taskArns[0]' --output text 2>/dev/null || echo "")
    if [ -n "$TASK_ARN" ] && [ "$TASK_ARN" != "None" ]; then
        ENI_ID=$(aws ecs describe-tasks --cluster "$CLUSTER_NAME" --tasks "$TASK_ARN" --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text 2>/dev/null || echo "")
        if [ -n "$ENI_ID" ] && [ "$ENI_ID" != "None" ]; then
            CURRENT_IP=$(aws ec2 describe-network-interfaces --network-interface-ids "$ENI_ID" --query 'NetworkInterfaces[0].Association.PublicIp' --output text 2>/dev/null || echo "")
        fi
    fi
fi

# Apply again with current IP if we got one
if [ -n "$CURRENT_IP" ] && [ "$CURRENT_IP" != "None" ]; then
    echo "🔄 Updating Terraform with current ECS IP: $CURRENT_IP"
    terraform plan -var="ecs_task_ip=$CURRENT_IP" -out=tfplan-with-ip
    terraform apply tfplan-with-ip
fi

echo -e "${GREEN}✅ Terraform deployment completed${NC}"

# ================================================================
# Step 3: Get Current ECS Task IP (Mirror GitHub Actions logic)
# ================================================================
echo -e "${YELLOW}📋 Step 3: Updating DNS with Current ECS Task IP${NC}"

echo "⏳ Waiting for ECS service to stabilize..."
sleep 30

# Get the current running task ARN
echo "🔍 Getting current ECS task..."
TASK_ARN=$(aws ecs list-tasks \
  --cluster "$CLUSTER_NAME" \
  --service-name "$SERVICE_NAME" \
  --query 'taskArns[0]' \
  --output text)

if [ "$TASK_ARN" == "None" ] || [ -z "$TASK_ARN" ]; then
    echo -e "${RED}❌ No running tasks found!${NC}"
    exit 1
fi

echo "📋 Task ARN: $TASK_ARN"

# Get network interface ID from task
ENI_ID=$(aws ecs describe-tasks \
  --cluster "$CLUSTER_NAME" \
  --tasks "$TASK_ARN" \
  --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' \
  --output text)

if [ -z "$ENI_ID" ]; then
    echo -e "${RED}❌ Could not get network interface ID!${NC}"
    exit 1
fi

echo "🔌 Network Interface: $ENI_ID"

# Get public IP from network interface
CURRENT_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids "$ENI_ID" \
  --query 'NetworkInterfaces[0].Association.PublicIp' \
  --output text)

if [ "$CURRENT_IP" == "None" ] || [ -z "$CURRENT_IP" ]; then
    echo -e "${RED}❌ Could not get public IP!${NC}"
    exit 1
fi

echo -e "${GREEN}🌐 Current ECS Task IP: $CURRENT_IP${NC}"

# ================================================================
# Step 4: Update DNS Record (Mirror GitHub Actions logic)
# ================================================================
echo -e "${YELLOW}📋 Step 4: Updating DNS Record${NC}"

# Get current DNS IP
DNS_IP=$(dig +short "$ECS_DIRECT_DOMAIN" | head -1)

echo "🔗 DNS Currently Points to: $DNS_IP"

if [ "$CURRENT_IP" = "$DNS_IP" ]; then
    echo -e "${GREEN}✅ DNS already points to current ECS task!${NC}"
else
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
    echo "⏳ Waiting for DNS propagation..."
    
    aws route53 wait resource-record-sets-changed --id "$CHANGE_ID"
    
    echo -e "${GREEN}✅ DNS update completed!${NC}"
fi

# ================================================================
# Step 5: Health Check
# ================================================================
echo -e "${YELLOW}📋 Step 5: Health Check${NC}"

echo "🔍 Testing direct IP access..."
if curl -f --max-time 10 "http://$CURRENT_IP:8000/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Direct IP health check passed!${NC}"
else
    echo -e "${YELLOW}⚠️  Direct IP not responding yet, waiting...${NC}"
    sleep 30
    if curl -f --max-time 10 "http://$CURRENT_IP:8000/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Direct IP health check now passed!${NC}"
    else
        echo -e "${RED}❌ Direct IP health check failed${NC}"
    fi
fi

echo "🔍 Testing CloudFront domain..."
if curl -f --max-time 10 "https://aldous-api.neobotnet.com/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ CloudFront domain health check passed!${NC}"
else
    echo -e "${YELLOW}⚠️  CloudFront domain not responding yet (DNS propagation may take time)${NC}"
fi

# ================================================================
# Summary
# ================================================================
echo ""
echo -e "${GREEN}🎯 DEPLOYMENT COMPLETED SUCCESSFULLY!${NC}"
echo ""
echo "📊 Summary:"
echo "  ├── ECS Task IP: $CURRENT_IP"
echo "  ├── DNS Record: $ECS_DIRECT_DOMAIN → $CURRENT_IP"
echo "  ├── Direct API: http://$CURRENT_IP:8000"
echo "  └── HTTPS API: https://aldous-api.neobotnet.com"
echo ""
echo "🔍 Quick verification commands:"
echo "  ├── curl http://$CURRENT_IP:8000/health"
echo "  ├── curl https://aldous-api.neobotnet.com/health"
echo "  └── curl https://aldous-api.neobotnet.com/api/v1/recon/health"
echo ""
echo -e "${BLUE}💡 Your deployment is now consistent with GitHub Actions!${NC}"
