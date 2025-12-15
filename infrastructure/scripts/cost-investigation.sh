#!/bin/bash

# ================================================================
# Cost Investigation Script
# Analyzes AWS costs and identifies orphaned infrastructure
# ================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}🚨 COST INVESTIGATION: Aug 1-18, 2025${NC}"
echo -e "${RED}======================================${NC}"

echo "📊 Total Costs: \$69.50 for 18 days (projected \$120/month)"
echo "🎯 Expected: ~\$18-21/month"
echo "💸 Overrun: ~\$100/month (500% over budget)"

echo -e "\n${YELLOW}🔍 DETAILED COST BREAKDOWN:${NC}"
echo "================================"

# Major cost items from costs.csv analysis
echo "💰 Top Cost Drivers:"
echo "  1. NAT Gateway Hours: \$41.70 (60%) 🚨"
echo "  2. Fargate vCPU: \$9.28 (13%) ✅"
echo "  3. Public IPv4: \$6.91 (10%) ⚠️"
echo "  4. Redis cache.t3.micro: \$5.14 (7%) ✅"
echo "  5. NAT Gateway Data: \$2.88 (4%) 🚨"
echo "  6. Fargate Memory: \$2.04 (3%) ✅"
echo "  7. Load Balancer: \$0.83 (1%) ⚠️"

echo -e "\n${RED}🚨 CRITICAL ISSUES IDENTIFIED:${NC}"
echo "1. NAT Gateway charges despite Terraform having them commented out"
echo "2. Load Balancer charges despite ultra-minimal architecture"
echo "3. Multiple Public IPv4 addresses suggesting orphaned Elastic IPs"

echo -e "\n${BLUE}🔍 AWS INFRASTRUCTURE INVESTIGATION${NC}"
echo "===================================="

# ================================================================
# 1. Check for NAT Gateways
# ================================================================
echo -e "\n${YELLOW}1. Checking NAT Gateways (Should be ZERO):${NC}"

regions="us-east-1 us-west-1 us-west-2"
nat_found=false

for region in $regions; do
    echo "🔍 Checking region: $region"
    
    nat_gateways=$(aws ec2 describe-nat-gateways \
        --region "$region" \
        --query 'NatGateways[?State!=`deleted`].[NatGatewayId,State,CreateTime,VpcId]' \
        --output table 2>/dev/null || echo "No access or no NAT gateways")
    
    if [[ "$nat_gateways" != *"None"* ]] && [[ "$nat_gateways" != "No access"* ]]; then
        echo -e "${RED}🚨 FOUND NAT GATEWAYS IN $region:${NC}"
        echo "$nat_gateways"
        nat_found=true
        
        # Calculate cost for this region
        nat_count=$(aws ec2 describe-nat-gateways --region "$region" --query 'NatGateways[?State!=`deleted`] | length' --output text 2>/dev/null || echo "0")
        if [ "$nat_count" -gt 0 ]; then
            echo "   💸 Cost Impact: $nat_count NAT Gateway(s) × \$0.045/hour = \$$(echo "$nat_count * 0.045 * 24" | bc) per day"
        fi
    else
        echo -e "${GREEN}   ✅ No NAT Gateways in $region${NC}"
    fi
done

# ================================================================
# 2. Check for Load Balancers
# ================================================================
echo -e "\n${YELLOW}2. Checking Load Balancers (Should be ZERO):${NC}"

for region in $regions; do
    echo "🔍 Checking ALBs in $region"
    
    albs=$(aws elbv2 describe-load-balancers \
        --region "$region" \
        --query 'LoadBalancers[*].[LoadBalancerName,LoadBalancerArn,Scheme,State.Code]' \
        --output table 2>/dev/null || echo "No access or no ALBs")
    
    if [[ "$albs" != *"None"* ]] && [[ "$albs" != "No access"* ]]; then
        echo -e "${RED}🚨 FOUND APPLICATION LOAD BALANCERS IN $region:${NC}"
        echo "$albs"
        
        # Get ALB count for cost calculation
        alb_count=$(aws elbv2 describe-load-balancers --region "$region" --query 'LoadBalancers | length' --output text 2>/dev/null || echo "0")
        if [ "$alb_count" -gt 0 ]; then
            echo "   💸 Cost Impact: $alb_count ALB(s) × \$0.0225/hour = \$$(echo "$alb_count * 0.0225 * 24" | bc) per day"
        fi
    else
        echo -e "${GREEN}   ✅ No ALBs in $region${NC}"
    fi
done

# ================================================================
# 3. Check for Unattached Elastic IPs
# ================================================================
echo -e "\n${YELLOW}3. Checking Unattached Elastic IPs:${NC}"

for region in $regions; do
    echo "🔍 Checking Elastic IPs in $region"
    
    # All Elastic IPs
    all_eips=$(aws ec2 describe-addresses \
        --region "$region" \
        --query 'Addresses[*].[PublicIp,AllocationId,AssociationId]' \
        --output table 2>/dev/null || echo "No access")
    
    # Unattached Elastic IPs
    unattached_eips=$(aws ec2 describe-addresses \
        --region "$region" \
        --query 'Addresses[?AssociationId==null].[PublicIp,AllocationId]' \
        --output table 2>/dev/null || echo "No access")
    
    if [[ "$all_eips" != *"None"* ]] && [[ "$all_eips" != "No access"* ]]; then
        echo "📍 All Elastic IPs in $region:"
        echo "$all_eips"
        
        if [[ "$unattached_eips" != *"None"* ]]; then
            echo -e "${RED}🚨 UNATTACHED ELASTIC IPs (costing \$0.005/hour each):${NC}"
            echo "$unattached_eips"
        fi
    else
        echo -e "${GREEN}   ✅ No Elastic IPs in $region${NC}"
    fi
done

# ================================================================
# 4. Check ECS Resources (Should exist)
# ================================================================
echo -e "\n${YELLOW}4. Checking ECS Resources (Expected):${NC}"

echo "🔍 Checking ECS Clusters:"
aws ecs list-clusters --region us-east-1 --query 'clusterArns[*]' --output table

echo -e "\n🔍 Checking ECS Services in neobotnet-v2-dev-cluster:"
aws ecs list-services --region us-east-1 --cluster neobotnet-v2-dev-cluster --query 'serviceArns[*]' --output table 2>/dev/null || echo "Cluster not found or no services"

# ================================================================
# 5. Check Redis Resources (Should exist)
# ================================================================
echo -e "\n${YELLOW}5. Checking Redis Resources (Expected):${NC}"

echo "🔍 Checking ElastiCache clusters:"
aws elasticache describe-cache-clusters --region us-east-1 --query 'CacheClusters[*].[CacheClusterId,CacheNodeType,Engine,CacheClusterStatus]' --output table

# ================================================================
# 6. Check CloudFront (Should exist)
# ================================================================
echo -e "\n${YELLOW}6. Checking CloudFront Distributions:${NC}"

echo "🔍 Checking CloudFront distributions:"
aws cloudfront list-distributions --query 'DistributionList.Items[*].[Id,DomainName,Status]' --output table

# ================================================================
# 7. Compare with Terraform State
# ================================================================
echo -e "\n${YELLOW}7. Terraform State Comparison:${NC}"

if [ -d "infrastructure/terraform" ]; then
    cd infrastructure/terraform
    
    if [ -d ".terraform" ]; then
        echo "📋 Resources in Terraform state:"
        terraform state list | sort
        
        echo -e "\n🔍 Checking for NAT Gateway references in state:"
        if terraform state list | grep -i nat; then
            echo -e "${RED}🚨 Found NAT Gateway resources in Terraform state!${NC}"
        else
            echo -e "${GREEN}✅ No NAT Gateway resources in Terraform state${NC}"
        fi
        
        echo -e "\n🔍 Checking for ALB references in state:"
        if terraform state list | grep -i "lb\|load.*balancer"; then
            echo -e "${RED}🚨 Found Load Balancer resources in Terraform state!${NC}"
        else
            echo -e "${GREEN}✅ No Load Balancer resources in Terraform state${NC}"
        fi
    else
        echo "⚠️ Terraform not initialized"
    fi
    
    cd - > /dev/null
fi

# ================================================================
# 8. Cost Analysis Summary
# ================================================================
echo -e "\n${BLUE}💰 COST ANALYSIS SUMMARY${NC}"
echo "========================="

echo "📊 18-day costs (Aug 1-18, 2025): \$69.50"
echo "📈 Monthly projection: \$119.72"
echo "🎯 Target monthly cost: \$18-21"
echo "💸 Monthly overspend: ~\$100 (500%)"

echo -e "\n🎯 Root Cause Analysis:"
echo "  • NAT Gateway Hours (\$41.70): Orphaned NAT Gateways despite Terraform removal"
echo "  • Public IPv4 (\$6.91): Multiple IPs, likely from NAT Gateway Elastic IPs"
echo "  • Load Balancer (\$0.83): Orphaned ALB despite ultra-minimal architecture"
echo "  • NAT Data Processing (\$2.88): Data flowing through orphaned NAT Gateways"

echo -e "\n${RED}🚨 IMMEDIATE ACTIONS NEEDED:${NC}"
echo "1. Delete orphaned NAT Gateways: \$41.70/month savings"
echo "2. Delete orphaned Load Balancers: \$0.83/month savings"
echo "3. Release unattached Elastic IPs: ~\$4/month savings"
echo "4. Clean up Terraform state if needed"

echo -e "\n${GREEN}🎯 Expected result: Reduce monthly costs to \$18-21 (82% reduction)${NC}"

echo -e "\n${YELLOW}💡 Next Steps:${NC}"
echo "1. Run ./infrastructure/scripts/cost-emergency-cleanup.sh"
echo "2. Verify cleanup with this script"
echo "3. Monitor costs for next billing period"
echo "4. Set up cost monitoring alerts"
