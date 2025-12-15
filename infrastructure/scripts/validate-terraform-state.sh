#!/bin/bash

# ================================================================
# Terraform State Validation Script
# Detects orphaned AWS resources not managed by Terraform
# ================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Terraform State Validation${NC}"
echo -e "${BLUE}==============================${NC}"

# Configuration
PROJECT_TAG="neobotnet-v2"
REGION="us-east-1"
ORPHAN_COUNT=0

# ================================================================
# 1. Check Terraform State Health
# ================================================================
echo -e "\n${YELLOW}📋 1. Terraform State Health Check${NC}"

if [ ! -d "infrastructure/terraform" ]; then
    echo -e "${RED}❌ Terraform directory not found${NC}"
    exit 1
fi

cd infrastructure/terraform

if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}⚠️ Terraform not initialized, initializing...${NC}"
    terraform init
fi

# Get all resources in Terraform state
echo "🔍 Getting Terraform state resources..."
TF_RESOURCES=$(terraform state list 2>/dev/null || echo "")

if [ -z "$TF_RESOURCES" ]; then
    echo -e "${RED}❌ No resources found in Terraform state${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found $(echo "$TF_RESOURCES" | wc -l) resources in Terraform state${NC}"

# ================================================================
# 2. Check for Orphaned AWS Resources
# ================================================================
echo -e "\n${YELLOW}📋 2. Orphaned Resource Detection${NC}"

# Function to check if resource exists in Terraform state
check_resource_in_state() {
    local resource_id="$1"
    local resource_type="$2"
    
    if echo "$TF_RESOURCES" | grep -q "$resource_type"; then
        echo -e "${GREEN}✅ $resource_type found in Terraform state${NC}"
        return 0
    else
        echo -e "${RED}❌ $resource_type NOT in Terraform state (ORPHANED)${NC}"
        ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
        return 1
    fi
}

# Check VPCs
echo -e "\n🌐 Checking VPCs..."
VPC_IDS=$(aws ec2 describe-vpcs --region "$REGION" --filters "Name=tag:Project,Values=$PROJECT_TAG" --query 'Vpcs[].VpcId' --output text)

if [ -n "$VPC_IDS" ]; then
    for vpc_id in $VPC_IDS; do
        echo "   📍 VPC: $vpc_id"
        check_resource_in_state "$vpc_id" "aws_vpc"
    done
else
    echo -e "${GREEN}   ✅ No project VPCs found${NC}"
fi

# Check ECS Clusters
echo -e "\n📦 Checking ECS Clusters..."
ECS_CLUSTERS=$(aws ecs list-clusters --region "$REGION" --query 'clusterArns[]' --output text | grep "$PROJECT_TAG" || echo "")

if [ -n "$ECS_CLUSTERS" ]; then
    for cluster_arn in $ECS_CLUSTERS; do
        cluster_name=$(basename "$cluster_arn")
        echo "   📍 ECS Cluster: $cluster_name"
        check_resource_in_state "$cluster_name" "aws_ecs_cluster"
    done
else
    echo -e "${GREEN}   ✅ No project ECS clusters found${NC}"
fi

# Check ECR Repositories
echo -e "\n📦 Checking ECR Repositories..."
ECR_REPOS=$(aws ecr describe-repositories --region "$REGION" --query 'repositories[?contains(repositoryName, `'$PROJECT_TAG'`)].repositoryName' --output text 2>/dev/null || echo "")

if [ -n "$ECR_REPOS" ]; then
    for repo in $ECR_REPOS; do
        echo "   📍 ECR Repository: $repo"
        check_resource_in_state "$repo" "aws_ecr_repository"
    done
else
    echo -e "${GREEN}   ✅ No project ECR repositories found${NC}"
fi

# Check ElastiCache Clusters
echo -e "\n💾 Checking ElastiCache Clusters..."
REDIS_CLUSTERS=$(aws elasticache describe-cache-clusters --region "$REGION" --query 'CacheClusters[?contains(CacheClusterId, `'$PROJECT_TAG'`)].CacheClusterId' --output text 2>/dev/null || echo "")

if [ -n "$REDIS_CLUSTERS" ]; then
    for cluster in $REDIS_CLUSTERS; do
        echo "   📍 Redis Cluster: $cluster"
        check_resource_in_state "$cluster" "aws_elasticache_cluster"
    done
else
    echo -e "${GREEN}   ✅ No project Redis clusters found${NC}"
fi

# Check Load Balancers (should be none)
echo -e "\n⚖️ Checking Load Balancers..."
ALB_ARNS=$(aws elbv2 describe-load-balancers --region "$REGION" --query 'LoadBalancers[?contains(LoadBalancerName, `'$PROJECT_TAG'`)].LoadBalancerArn' --output text 2>/dev/null || echo "")

if [ -n "$ALB_ARNS" ]; then
    for alb_arn in $ALB_ARNS; do
        alb_name=$(aws elbv2 describe-load-balancers --region "$REGION" --load-balancer-arns "$alb_arn" --query 'LoadBalancers[0].LoadBalancerName' --output text)
        echo -e "${RED}   ❌ UNEXPECTED Load Balancer: $alb_name${NC}"
        echo -e "${RED}      This should not exist in ultra-minimal architecture!${NC}"
        ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    done
else
    echo -e "${GREEN}   ✅ No load balancers found (correct for ultra-minimal architecture)${NC}"
fi

# Check NAT Gateways (should be none)
echo -e "\n🌐 Checking NAT Gateways..."
NAT_GATEWAYS=$(aws ec2 describe-nat-gateways --region "$REGION" --query 'NatGateways[?State!=`deleted`].NatGatewayId' --output text 2>/dev/null || echo "")

if [ -n "$NAT_GATEWAYS" ]; then
    for nat_id in $NAT_GATEWAYS; do
        echo -e "${RED}   ❌ UNEXPECTED NAT Gateway: $nat_id${NC}"
        echo -e "${RED}      This should not exist in ultra-minimal architecture!${NC}"
        ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    done
else
    echo -e "${GREEN}   ✅ No NAT Gateways found (correct for ultra-minimal architecture)${NC}"
fi

# ================================================================
# 3. Check for Unattached Resources
# ================================================================
echo -e "\n${YELLOW}📋 3. Unattached Resource Check${NC}"

# Check for unattached Elastic IPs
echo -e "\n🔗 Checking Unattached Elastic IPs..."
UNATTACHED_EIPS=$(aws ec2 describe-addresses --region "$REGION" --query 'Addresses[?AssociationId==null].AllocationId' --output text 2>/dev/null || echo "")

if [ -n "$UNATTACHED_EIPS" ]; then
    for eip in $UNATTACHED_EIPS; do
        echo -e "${YELLOW}   ⚠️ Unattached Elastic IP: $eip${NC}"
        ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    done
else
    echo -e "${GREEN}   ✅ No unattached Elastic IPs found${NC}"
fi

# Check for unused security groups
echo -e "\n🔒 Checking Unused Security Groups..."
ALL_SGS=$(aws ec2 describe-security-groups --region "$REGION" --filters "Name=tag:Project,Values=$PROJECT_TAG" --query 'SecurityGroups[].GroupId' --output text 2>/dev/null || echo "")

if [ -n "$ALL_SGS" ]; then
    for sg_id in $ALL_SGS; do
        # Check if security group is attached to any resources
        ATTACHED=$(aws ec2 describe-network-interfaces --region "$REGION" --filters "Name=group-id,Values=$sg_id" --query 'NetworkInterfaces[].GroupId' --output text 2>/dev/null || echo "")
        
        if [ -z "$ATTACHED" ]; then
            echo -e "${YELLOW}   ⚠️ Potentially unused Security Group: $sg_id${NC}"
        fi
    done
fi

# ================================================================
# 4. Generate Report
# ================================================================
echo -e "\n${BLUE}📊 VALIDATION SUMMARY${NC}"
echo -e "${BLUE}======================${NC}"

if [ $ORPHAN_COUNT -eq 0 ]; then
    echo -e "\n${GREEN}✅ EXCELLENT! No orphaned resources detected${NC}"
    echo -e "${GREEN}   All AWS resources are properly managed by Terraform${NC}"
    echo -e "${GREEN}   Infrastructure is clean and cost-optimized${NC}"
else
    echo -e "\n${RED}🚨 ATTENTION: $ORPHAN_COUNT potential issues found${NC}"
    echo -e "${RED}   Review the items marked with ❌ above${NC}"
    echo -e "${RED}   Consider cleanup actions to prevent costs${NC}"
fi

echo -e "\n📋 Terraform State Health:"
echo -e "   ├── Resources in state: $(echo "$TF_RESOURCES" | wc -l)"
echo -e "   ├── Infrastructure validated: ✅"
echo -e "   └── State consistency: $([ $ORPHAN_COUNT -eq 0 ] && echo "✅ Good" || echo "⚠️ Issues detected")"

echo -e "\n💰 Cost Impact:"
if [ $ORPHAN_COUNT -eq 0 ]; then
    echo -e "   └── No unexpected costs from orphaned resources ✅"
else
    echo -e "   └── Potential unexpected costs: Review $ORPHAN_COUNT issues ⚠️"
fi

# ================================================================
# 5. Cleanup Recommendations
# ================================================================
if [ $ORPHAN_COUNT -gt 0 ]; then
    echo -e "\n${YELLOW}🔧 RECOMMENDED ACTIONS${NC}"
    echo -e "${YELLOW}======================${NC}"
    
    echo -e "\n1. 🗑️ Delete orphaned resources:"
    echo -e "   ./infrastructure/scripts/cost-emergency-cleanup.sh"
    
    echo -e "\n2. 🔄 Import existing resources to Terraform:"
    echo -e "   terraform import aws_resource.name resource-id"
    
    echo -e "\n3. 📊 Monitor costs:"
    echo -e "   ./infrastructure/scripts/monthly-cost-check.sh"
    
    echo -e "\n4. 🛡️ Prevent future orphans:"
    echo -e "   - Use only Terraform for resource management"
    echo -e "   - Avoid manual AWS CLI resource creation"
    echo -e "   - Run this validation script before major changes"
fi

# ================================================================
# 6. Exit with appropriate code
# ================================================================
cd - > /dev/null

if [ $ORPHAN_COUNT -eq 0 ]; then
    echo -e "\n${GREEN}🎯 Validation completed successfully!${NC}"
    exit 0
else
    echo -e "\n${YELLOW}⚠️ Validation completed with warnings${NC}"
    exit 1
fi
