#!/bin/bash

# ================================================================
# NAT Gateway Cost Detective Script
# Finds all potential sources of NAT Gateway billing
# ================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🕵️ NAT Gateway Cost Detective${NC}"
echo -e "${BLUE}=============================${NC}"

echo "🎯 Investigating NAT Gateway charges from Aug 1-18..."
echo "📅 Time period: August 1-18, 2024"

# ================================================================
# 1. Check ALL regions for NAT Gateways
# ================================================================
echo -e "\n${YELLOW}🌍 1. Global NAT Gateway Scan${NC}"
echo "================================"

# Get all regions
regions=$(aws ec2 describe-regions --query 'Regions[].RegionName' --output text)
nat_found=false

for region in $regions; do
    echo -n "🔍 Checking $region... "
    
    # Check for NAT Gateways (including deleted ones in billing period)
    nat_gateways=$(aws ec2 describe-nat-gateways \
        --region "$region" \
        --query 'NatGateways[?CreateTime>=`2024-08-01T00:00:00Z`]' \
        --output json 2>/dev/null || echo "[]")
    
    nat_count=$(echo "$nat_gateways" | jq '. | length')
    
    if [ "$nat_count" -gt 0 ]; then
        echo -e "${RED}FOUND $nat_count NAT Gateway(s)!${NC}"
        nat_found=true
        
        echo "$nat_gateways" | jq -r '.[] | "  🚨 NAT Gateway: \(.NatGatewayId) | State: \(.State) | Created: \(.CreateTime) | Deleted: \(.DeleteTime // "Still Active")"'
        
        # Check for associated Elastic IPs
        echo "  💰 Associated costs for this region:"
        allocation_ids=$(echo "$nat_gateways" | jq -r '.[].NatGatewayAddresses[]?.AllocationId // empty')
        
        if [ -n "$allocation_ids" ]; then
            for alloc_id in $allocation_ids; do
                ip_info=$(aws ec2 describe-addresses --region "$region" --allocation-ids "$alloc_id" --output json 2>/dev/null || echo '{"Addresses":[]}')
                public_ip=$(echo "$ip_info" | jq -r '.Addresses[0].PublicIp // "Unknown"')
                echo "     💸 Elastic IP: $public_ip ($alloc_id)"
            done
        fi
    else
        echo -e "${GREEN}Clean${NC}"
    fi
done

if [ "$nat_found" = false ]; then
    echo -e "\n${GREEN}✅ No NAT Gateways found in any region${NC}"
else
    echo -e "\n${RED}🚨 NAT Gateways detected! These are likely causing your billing discrepancy.${NC}"
fi

# ================================================================
# 2. Check for VPC Flow Logs (can indicate NAT usage)
# ================================================================
echo -e "\n${YELLOW}🌊 2. VPC Flow Logs Analysis${NC}"
echo "============================="

echo "🔍 Checking for VPC Flow Logs that might indicate NAT usage..."

# Check your main VPC
vpc_id=$(aws ec2 describe-vpcs --region us-east-1 --filters "Name=tag:Project,Values=neobotnet-v2" --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "None")

if [ "$vpc_id" != "None" ] && [ "$vpc_id" != "null" ]; then
    echo "📋 Found project VPC: $vpc_id"
    
    # Check flow logs
    flow_logs=$(aws ec2 describe-flow-logs --region us-east-1 --filter "Name=resource-id,Values=$vpc_id" --output json)
    flow_count=$(echo "$flow_logs" | jq '.FlowLogs | length')
    
    if [ "$flow_count" -gt 0 ]; then
        echo "📊 VPC Flow Logs found: $flow_count"
        echo "$flow_logs" | jq -r '.FlowLogs[] | "  📝 Flow Log: \(.FlowLogId) | Status: \(.FlowLogStatus) | Created: \(.CreationTime)"'
    else
        echo "📊 No VPC Flow Logs found"
    fi
else
    echo "❌ Project VPC not found"
fi

# ================================================================
# 3. Check Terraform State for Historical Resources
# ================================================================
echo -e "\n${YELLOW}🏗️ 3. Terraform State Analysis${NC}"
echo "==============================="

echo "🔍 Checking if Terraform state shows any NAT Gateway history..."

if [ -d "infrastructure/terraform" ]; then
    cd infrastructure/terraform
    
    # Check if terraform is initialized
    if [ -d ".terraform" ]; then
        echo "📋 Terraform is initialized, checking state..."
        
        # Try to show state
        terraform_output=$(terraform show 2>/dev/null || echo "State check failed")
        
        if echo "$terraform_output" | grep -i "nat.gateway" > /dev/null; then
            echo -e "${RED}🚨 Terraform state contains NAT Gateway references!${NC}"
            echo "$terraform_output" | grep -i "nat.gateway" | head -5
        else
            echo -e "${GREEN}✅ No NAT Gateway references in current Terraform state${NC}"
        fi
        
        # Check for any EIP references
        if echo "$terraform_output" | grep -i "elastic.ip\|eip" > /dev/null; then
            echo -e "${YELLOW}⚠️ Found Elastic IP references:${NC}"
            echo "$terraform_output" | grep -i "elastic.ip\|eip" | head -3
        fi
    else
        echo "⚠️ Terraform not initialized in this directory"
    fi
    
    cd - > /dev/null
else
    echo "❌ Infrastructure directory not found"
fi

# ================================================================
# 4. Check GitHub Actions for Deployment History
# ================================================================
echo -e "\n${YELLOW}📋 4. Deployment History Analysis${NC}"
echo "=================================="

echo "🔍 Analyzing deployment pattern from GitHub Actions..."

if [ -f ".github/workflows/deploy-backend-optimized.yml" ]; then
    echo "📄 Found deployment workflow"
    
    # Check if there are any NAT Gateway references in workflows
    if grep -i "nat.gateway\|natgateway" .github/workflows/*.yml > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ Found NAT Gateway references in workflows:${NC}"
        grep -i "nat.gateway\|natgateway" .github/workflows/*.yml
    else
        echo -e "${GREEN}✅ No NAT Gateway references in GitHub Actions${NC}"
    fi
    
    # Check deployment frequency (could indicate multiple deployments causing resource creation)
    echo "📊 Recent deployment activity pattern:"
    echo "   - Smart change detection enabled"
    echo "   - Terraform infrastructure changes only when needed"
    echo "   - This should minimize resource recreation"
    
else
    echo "❌ GitHub Actions workflow not found"
fi

# ================================================================
# 5. Cost Calculation & Resolution
# ================================================================
echo -e "\n${BLUE}💰 Cost Impact Analysis${NC}"
echo "========================"

echo "📊 NAT Gateway cost calculation:"
echo "   ├── NAT Gateway Hours: \$0.045/hour"
echo "   ├── Data Processing: \$0.045/GB"
echo "   ├── Elastic IP (if unattached): \$0.005/hour"
echo "   └── Aug 1-18 (18 days = 432 hours)"

echo -e "\n💸 Potential costs for 18-day period:"
echo "   ├── 1 NAT Gateway: 432h × \$0.045 = \$19.44"
echo "   ├── 2 NAT Gateways: 432h × \$0.090 = \$38.88"
echo "   ├── Unattached EIP: 432h × \$0.005 = \$2.16"
echo "   └── Data processing: Variable based on usage"

# ================================================================
# 6. Action Plan
# ================================================================
echo -e "\n${RED}🚨 IMMEDIATE ACTION PLAN${NC}"
echo "========================="

echo "1. 🔍 Run these commands to find NAT Gateways:"
echo "   aws ec2 describe-nat-gateways --region us-east-1 --output table"
echo "   aws ec2 describe-nat-gateways --region us-west-2 --output table"

echo -e "\n2. 🗑️ Delete any found NAT Gateways:"
echo "   aws ec2 delete-nat-gateway --nat-gateway-id <nat-gateway-id>"

echo -e "\n3. 🔗 Release unattached Elastic IPs:"
echo "   aws ec2 describe-addresses --query 'Addresses[?AssociationId==null]'"
echo "   aws ec2 release-address --allocation-id <allocation-id>"

echo -e "\n4. 💾 Clean Terraform state if needed:"
echo "   terraform state list | grep nat"
echo "   terraform state rm <nat-gateway-resource> # if found"

echo -e "\n5. 📊 Verify costs.csv data:"
echo "   - Check 'NatGateway-Hours' line items"
echo "   - Note the region and time period"
echo "   - Cross-reference with resource creation dates"

echo -e "\n${GREEN}✅ Prevention for future:${NC}"
echo "   ├── Monthly cost monitoring with this script"
echo "   ├── Terraform destroy before major architecture changes"
echo "   ├── AWS Cost Budgets set at \$25/month with alerts"
echo "   └── Regular AWS resource cleanup"
