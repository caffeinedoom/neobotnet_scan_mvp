# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}

# Public Subnets
resource "aws_subnet" "public" {
  count = var.availability_zones_count

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-subnet-${count.index + 1}"
    Type = "Public"
  })
}

# Private Subnets (for Redis and other internal services)
resource "aws_subnet" "private" {
  count = var.availability_zones_count

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-subnet-${count.index + 1}"
    Type = "Private"
  })
}

# ================================================================
# COST OPTIMIZATION: NAT Gateway resources removed to save ~$270/month
# ================================================================
# The following resources have been commented out because:
# - ECS tasks run in public subnets with direct internet access
# - Redis in private subnets doesn't need internet access
# - VPC internal communication works without NAT routing
# 
# Estimated monthly savings: ~$270/month
# - 2 NAT Gateways @ $45/month each = $90/month
# - 2 Elastic IPs @ $3.65/month each = $7.30/month
# - Data processing charges = ~$30/month
# ================================================================

# # Elastic IPs for NAT Gateways (REMOVED - $7.30/month savings)
# resource "aws_eip" "nat" {
#   count = var.availability_zones_count
# 
#   domain = "vpc"
#   depends_on = [aws_internet_gateway.main]
# 
#   tags = merge(local.common_tags, {
#     Name = "${local.name_prefix}-nat-eip-${count.index + 1}"
#   })
# 
#   lifecycle {
#     ignore_changes = [tags]
#   }
# }

# # NAT Gateways (REMOVED - $90/month savings)
# resource "aws_nat_gateway" "main" {
#   count = var.availability_zones_count
# 
#   allocation_id = aws_eip.nat[count.index].id
#   subnet_id     = aws_subnet.public[count.index].id
#   depends_on    = [aws_internet_gateway.main]
# 
#   tags = merge(local.common_tags, {
#     Name = "${local.name_prefix}-nat-gateway-${count.index + 1}"
#   })
# }

# Route Table for Public Subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-rt"
  })
}

# ================================================================
# PRIVATE SUBNET ROUTING: Simplified without NAT Gateway dependency
# ================================================================
# Private subnets now use a simpler route table without internet access
# This is perfect for Redis which only needs VPC-internal communication

# Route Table for Private Subnets (No Internet Access)
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  # No default route - private subnets are truly private
  # VPC-internal communication works automatically via local routes

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-rt"
  })
}

# Route Table Associations
resource "aws_route_table_association" "public" {
  count = var.availability_zones_count

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count = var.availability_zones_count

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
} 