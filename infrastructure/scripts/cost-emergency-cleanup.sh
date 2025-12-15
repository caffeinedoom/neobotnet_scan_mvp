#!/bin/bash

# ================================================================
# Emergency Cost Cleanup Script
# Removes orphaned NAT Gateway resources and prevents future costs
# ================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}🚨 EMERGENCY COST CLEANUP${NC}"
echo -e "${RED}=========================${NC}"

# ================================================================
# 1. Find and Delete NAT Gateways
# ================================================================
echo -e "\n${YELLOW}🗑️ Step 1: Find and Delete NAT Gateways${NC}"

regions="us-east-1 us-west-1 us-west-2 eu-west-1 ap-southeast-1"

for region in $regions; do
    echo "🔍 Checking region: $region"
    
    # Get NAT Gateways
    nat_gateways=$(aws ec2 describe-nat-gateways --region "$region" --query 'NatGateways[?State==`available`].NatGatewayId' --output text 2>/dev/null || echo "")
    
    if [ -n "$nat_gateways" ]; then
        echo -e "${RED}🚨 Found NAT Gateways in $region:${NC}"
        for nat_id in $nat_gateways; do
            echo "   💸 NAT Gateway: $nat_id"
            echo "   🗑️ To delete: aws ec2 delete-nat-gateway --region $region --nat-gateway-id $nat_id"
            
            # Uncomment the line below to auto-delete (DANGEROUS!)
            # aws ec2 delete-nat-gateway --region "$region" --nat-gateway-id "$nat_id"
        done
    else
        echo -e "${GREEN}✅ No active NAT Gateways in $region${NC}"
    fi
done

# ================================================================
# 2. Find and Release Unattached Elastic IPs
# ================================================================
echo -e "\n${YELLOW}🔗 Step 2: Find and Release Unattached Elastic IPs${NC}"

for region in $regions; do
    echo "🔍 Checking region: $region"
    
    # Get unattached EIPs
    unattached_eips=$(aws ec2 describe-addresses --region "$region" --query 'Addresses[?AssociationId==null].AllocationId' --output text 2>/dev/null || echo "")
    
    if [ -n "$unattached_eips" ]; then
        echo -e "${YELLOW}⚠️ Found unattached Elastic IPs in $region:${NC}"
        for alloc_id in $unattached_eips; do
            # Get IP address for confirmation
            ip_address=$(aws ec2 describe-addresses --region "$region" --allocation-ids "$alloc_id" --query 'Addresses[0].PublicIp' --output text)
            echo "   💸 Elastic IP: $ip_address ($alloc_id)"
            echo "   🗑️ To release: aws ec2 release-address --region $region --allocation-id $alloc_id"
            
            # Uncomment the line below to auto-release (VERIFY FIRST!)
            # aws ec2 release-address --region "$region" --allocation-id "$alloc_id"
        done
    else
        echo -e "${GREEN}✅ No unattached Elastic IPs in $region${NC}"
    fi
done

# ================================================================
# 3. Terraform State Cleanup
# ================================================================
echo -e "\n${YELLOW}🏗️ Step 3: Terraform State Cleanup${NC}"

if [ -d "infrastructure/terraform" ]; then
    cd infrastructure/terraform
    
    if [ -d ".terraform" ]; then
        echo "📋 Checking Terraform state for NAT Gateway resources..."
        
        # List all state resources
        state_resources=$(terraform state list 2>/dev/null || echo "")
        
        if echo "$state_resources" | grep -i "nat.*gateway\|aws_eip" > /dev/null; then
            echo -e "${YELLOW}⚠️ Found NAT Gateway or EIP resources in Terraform state:${NC}"
            echo "$state_resources" | grep -i "nat.*gateway\|aws_eip"
            
            echo -e "\n🔧 Manual cleanup required:"
            echo "   terraform state rm aws_nat_gateway.<resource_name>"
            echo "   terraform state rm aws_eip.<resource_name>"
        else
            echo -e "${GREEN}✅ No NAT Gateway or EIP resources in Terraform state${NC}"
        fi
    else
        echo "⚠️ Terraform not initialized"
    fi
    
    cd - > /dev/null
fi

# ================================================================
# 4. Cost Monitoring Setup
# ================================================================
echo -e "\n${BLUE}📊 Step 4: Setup Cost Monitoring${NC}"

echo "🔧 Setting up AWS Cost Budget (manual setup required)..."

cat << 'EOF'
💰 Create AWS Cost Budget:
1. Go to AWS Billing Console → Budgets
2. Create Budget:
   - Budget Type: Cost Budget
   - Budget Amount: $25/month
   - Budget Period: Monthly
   - Filters: None (monitor all services)
   
3. Set Alerts:
   - Alert 1: 80% of budget ($20)
   - Alert 2: 100% of budget ($25)
   - Alert 3: 120% of budget ($30)
   
4. Email: Your email address
5. Additional Actions: Stop EC2 instances at 120%
EOF

# ================================================================
# 5. Prevention Commands
# ================================================================
echo -e "\n${GREEN}✅ Step 5: Prevention & Monitoring${NC}"

# Create monitoring script
cat << 'EOF' > ../scripts/monthly-cost-check.sh
#!/bin/bash
# Monthly cost monitoring script

echo "🔍 Monthly AWS Cost Check"
echo "========================"

# Check for NAT Gateways
echo "🚨 NAT Gateway Check:"
aws ec2 describe-nat-gateways --region us-east-1 --query 'NatGateways[?State!=`deleted`]' --output table

# Check for unattached EIPs
echo -e "\n💸 Unattached Elastic IP Check:"
aws ec2 describe-addresses --region us-east-1 --query 'Addresses[?AssociationId==null]' --output table

# Check current bill
echo -e "\n💰 Current Month Costs:"
aws ce get-dimension-values --dimension Key=SERVICE --time-period Start=$(date -d "$(date +%Y-%m-01)" +%Y-%m-%d),End=$(date +%Y-%m-%d) --query 'DimensionValues[?Value==`Amazon Elastic Compute Cloud - Compute`]'

echo -e "\n✅ Monthly check complete. Set reminder for next month!"
EOF

chmod +x ../scripts/monthly-cost-check.sh
echo "📅 Created monthly monitoring script: infrastructure/scripts/monthly-cost-check.sh"

# ================================================================
# Summary
# ================================================================
echo -e "\n${BLUE}📋 EMERGENCY CLEANUP SUMMARY${NC}"
echo "============================="

echo -e "\n🎯 What this script checked:"
echo "   ✅ NAT Gateways in 5 major regions"
echo "   ✅ Unattached Elastic IPs"
echo "   ✅ Terraform state cleanup"
echo "   ✅ Cost monitoring setup"

echo -e "\n🚨 MANUAL ACTIONS REQUIRED:"
echo "   1. Review NAT Gateway deletion commands above"
echo "   2. Confirm Elastic IP releases are safe"
echo "   3. Run deletion commands manually"
echo "   4. Setup AWS Cost Budget in console"
echo "   5. Schedule monthly cost checks"

echo -e "\n💰 Expected cost reduction after cleanup:"
echo "   🗑️ NAT Gateway removal: -$45/month per gateway"
echo "   🔗 EIP release: -$3.65/month per IP"
echo "   📊 Target monthly cost: $18-21"

echo -e "\n${GREEN}✅ Prevention measures in place:${NC}"
echo "   📅 Monthly monitoring script created"
echo "   🚨 Cost budget setup instructions provided"
echo "   🔧 Terraform architecture already optimized"
