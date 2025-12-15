# Application Load Balancer (ALB) Implementation Plan

**Created**: 2025-11-15  
**Purpose**: Fix intermittent 502 errors by adding ALB in front of ECS service  
**Status**: Planning Phase  

---

## **🎯 Executive Summary**

### **Current Architecture (Problematic)**
```
Client 
  → CloudFront (aldous-api.neobotnet.com)
    → Route53 DNS (ecs-direct.aldous-api.neobotnet.com, TTL=60s)
      → ECS Task (single, public IP changes on deploy)
        → Port 8000 (FastAPI)
```

### **Problems**
1. **DNS Propagation Lag**: 0-60s window where CloudFront has old IP
2. **No Health Checks**: Traffic routes to unhealthy tasks
3. **Single Point of Failure**: 1 task = no redundancy
4. **Deployment Disruption**: New task IP requires DNS update
5. **Manual DNS Management**: GitHub Actions script updates Route53

### **Target Architecture (Robust)**
```
Client
  → CloudFront (aldous-api.neobotnet.com)
    → ALB (neobotnet-v2-dev-alb-123456.us-east-1.elb.amazonaws.com)
      → Target Group (health checks: /health every 30s)
        → ECS Task 1 (primary, any IP)
        → ECS Task 2 (standby, rolling deployments)
```

### **Benefits**
✅ Stable ALB DNS (never changes)  
✅ Health checks before routing  
✅ 2+ tasks for redundancy  
✅ Zero-downtime deployments  
✅ No manual DNS updates  
✅ Industry standard architecture  

### **Costs**
- **ALB**: ~$16/month ($0.0225/hour)
- **LCU**: ~$7/month (estimated based on low traffic)
- **Total**: ~$23/month ($0.75/day)

---

## **📋 Current Infrastructure Analysis**

### **What Exists (from Terraform scan)**

#### **1. VPC & Networking** ✅
```hcl
# infrastructure/terraform/networking.tf
- VPC: 10.0.0.0/16
- Public Subnets: 2 AZs (us-east-1a, us-east-1b)
  - 10.0.0.0/24 (AZ1)
  - 10.0.1.0/24 (AZ2)
- Private Subnets: 2 AZs (for Redis)
- Internet Gateway: ✅ Attached
- NAT Gateway: ❌ Removed (cost optimization)
```

#### **2. ECS Service** ✅
```hcl
# infrastructure/terraform/ecs-batch-integration.tf
resource "aws_ecs_service" "main_batch" {
  name            = "neobotnet-v2-dev-service-batch"
  cluster         = "neobotnet-v2-dev-cluster"
  task_definition = "neobotnet-v2-dev-app-batch"
  desired_count   = 1  # Currently 1 task
  launch_type     = "FARGATE"
  
  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = aws_subnet.public[*].id  # ✅ Public subnets
    assign_public_ip = true                      # ✅ For internet access
  }
}
```

#### **3. Security Groups** ✅
```hcl
# infrastructure/terraform/security.tf
resource "aws_security_group" "ecs_tasks" {
  # Allows: 0.0.0.0/0:8000 → ECS tasks
  # Currently wide open for direct access
}
```

#### **4. CloudFront** ✅
```hcl
# infrastructure/terraform/cloudfront.tf
resource "aws_cloudfront_distribution" "api_distribution" {
  origin {
    domain_name = "ecs-direct.aldous-api.neobotnet.com"  # ❌ Dynamic DNS
    origin_id   = "neobotnet-v2-dev-api-origin"
    
    custom_origin_config {
      http_port              = 8000
      https_port             = 443
      origin_protocol_policy = "http-only"
      # ❌ Missing timeout configs
    }
  }
}
```

### **What's Missing**
❌ Application Load Balancer  
❌ ALB Target Group  
❌ ALB Security Group  
❌ ALB Listener (HTTP:80, HTTPS:443)  
❌ Target Group attachment to ECS service  
❌ Health check configuration  

---

## **🔧 Implementation Steps**

### **Step 1: Create ALB Security Group** (5 minutes)

**File**: `infrastructure/terraform/security.tf`

**Add**:
```hcl
# Security Group for ALB
resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id

  # Allow HTTP from anywhere (ALB handles HTTPS termination at CloudFront level)
  ingress {
    protocol    = "tcp"
    from_port   = 80
    to_port     = 80
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP from internet (CloudFront)"
  }

  # Allow HTTPS (optional, for direct ALB access)
  ingress {
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from internet"
  }

  # All outbound to ECS tasks
  egress {
    protocol    = "tcp"
    from_port   = var.app_port  # 8000
    to_port     = var.app_port
    cidr_blocks = [var.vpc_cidr]  # Only to VPC
    description = "To ECS tasks"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-alb-sg"
  })
}
```

**Modify** (restrict ECS tasks to only accept traffic from ALB):
```hcl
resource "aws_security_group" "ecs_tasks" {
  name_prefix = "${local.name_prefix}-ecs-tasks-"
  vpc_id      = aws_vpc.main.id

  # CHANGED: Only allow traffic from ALB (not 0.0.0.0/0)
  ingress {
    protocol        = "tcp"
    from_port       = var.app_port
    to_port         = var.app_port
    security_groups = [aws_security_group.alb.id]  # ✅ Only from ALB
    description     = "HTTP from ALB only"
  }

  # All outbound traffic (unchanged)
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecs-tasks-sg"
  })
}
```

---

### **Step 2: Create Application Load Balancer** (10 minutes)

**File**: `infrastructure/terraform/alb.tf` (new file)

**Create**:
```hcl
# ================================================================
# Application Load Balancer for ECS Service
# ================================================================

# ALB
resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false  # Internet-facing
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = false  # Set true for production
  enable_http2              = true
  enable_cross_zone_load_balancing = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-alb"
  })
}

# Target Group for ECS tasks
resource "aws_lb_target_group" "app" {
  name        = "${local.name_prefix}-tg"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"  # Fargate uses IP target type

  # Health check configuration
  health_check {
    enabled             = true
    healthy_threshold   = 2      # 2 successful checks = healthy
    unhealthy_threshold = 3      # 3 failed checks = unhealthy
    timeout             = 5      # Wait 5s for response
    interval            = 30     # Check every 30s
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"  # Expect 200 OK
  }

  # Deregistration delay (connection draining)
  deregistration_delay = 30  # Wait 30s before removing task

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-target-group"
  })
}

# HTTP Listener (forwards to target group)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# Output ALB DNS for CloudFront
output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the ALB (for Route53 alias)"
  value       = aws_lb.main.zone_id
}
```

---

### **Step 3: Update ECS Service to Use Target Group** (5 minutes)

**File**: `infrastructure/terraform/ecs-batch-integration.tf`

**Modify**:
```hcl
resource "aws_ecs_service" "main_batch" {
  name            = "${local.name_prefix}-service-batch"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app_batch.arn
  desired_count   = var.app_count  # Can now increase to 2+
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = aws_subnet.public[*].id
    assign_public_ip = true  # Keep for Redis/Supabase access
  }

  # ✅ ADD THIS: Register tasks with ALB target group
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"  # Must match container name in task definition
    container_port   = var.app_port
  }

  # ✅ ADD THIS: Wait for ALB to be healthy before routing traffic
  health_check_grace_period_seconds = 60

  depends_on = [
    aws_iam_role_policy_attachment.ecs_task_execution_role,
    aws_iam_role_policy.batch_orchestrator_policy,
    aws_lb_listener.http  # ✅ Wait for ALB listener
  ]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-batch-service"
  })
}
```

**Verify container name** in task definition:
```hcl
# In infrastructure/terraform/ecs-batch-integration.tf
resource "aws_ecs_task_definition" "app_batch" {
  # ...
  container_definitions = jsonencode([
    {
      name  = "app"  # ✅ Ensure this matches load_balancer.container_name
      # ...
    }
  ])
}
```

---

### **Step 4: Update CloudFront to Point to ALB** (5 minutes)

**File**: `infrastructure/terraform/cloudfront.tf`

**Modify**:
```hcl
resource "aws_cloudfront_distribution" "api_distribution" {
  origin {
    domain_name = aws_lb.main.dns_name  # ✅ Changed from ecs-direct DNS
    origin_id   = "${local.name_prefix}-api-origin"
    
    custom_origin_config {
      http_port                    = 80   # ALB listens on 80
      https_port                   = 443
      origin_protocol_policy       = "http-only"
      origin_ssl_protocols         = ["TLSv1.2"]
      
      # ✅ ADD THESE: Timeout configurations
      origin_read_timeout          = 60      # Max allowed
      origin_keepalive_timeout     = 60      # Keep connections alive
      origin_connection_attempts   = 3       # Retry on failure
      origin_connection_timeout    = 10      # Connect timeout
    }
  }

  # ... rest unchanged ...

  depends_on = [
    aws_acm_certificate_validation.api_cert,
    aws_lb.main  # ✅ Changed from aws_route53_record.ecs_direct
  ]
}
```

**Remove** (no longer needed):
```hcl
# DELETE THESE from cloudfront.tf:
# - variable "ecs_task_ip"
# - locals.ecs_direct_hostname
# - resource "aws_route53_record" "ecs_direct"
```

---

### **Step 5: Remove DNS Update from GitHub Actions** (5 minutes)

**File**: `.github/workflows/deploy-backend-optimized-improved.yml`

**Remove** entire "Enhanced DNS Update with Retry Logic" step (lines ~412-510):
```yaml
# DELETE THIS ENTIRE STEP:
- name: Enhanced DNS Update with Retry Logic
  run: |
    # ... (remove ~100 lines of DNS management code)
```

**Reasoning**: ALB DNS is stable, doesn't change on deployment.

---

### **Step 6: Optional - Increase ECS Task Count** (2 minutes)

**File**: `infrastructure/terraform/variables.tf`

**Modify**:
```hcl
variable "app_count" {
  description = "Number of docker containers to run"
  type        = number
  default     = 2  # ✅ Changed from 1 to 2 for redundancy
}
```

**Benefit**: 2 tasks = zero-downtime rolling deployments

**Cost**: +$50/month for additional Fargate task (0.5 vCPU + 1GB RAM)

---

## **🚀 Deployment Plan**

### **Pre-Deployment Checklist**
- [ ] Review all Terraform changes
- [ ] Backup current `terraform.tfstate`
- [ ] Test in staging environment (if available)
- [ ] Schedule maintenance window (optional, minimal downtime expected)

### **Deployment Steps**

#### **Phase 1: Infrastructure Update** (15 minutes)
```bash
cd infrastructure/terraform

# 1. Init (if new file added)
terraform init

# 2. Plan and review changes
terraform plan -out=tfplan

# Expected changes:
#   + aws_security_group.alb
#   ~ aws_security_group.ecs_tasks (modify ingress)
#   + aws_lb.main
#   + aws_lb_target_group.app
#   + aws_lb_listener.http
#   ~ aws_ecs_service.main_batch (add load_balancer block)
#   ~ aws_cloudfront_distribution.api_distribution (change origin)
#   - aws_route53_record.ecs_direct (removed)

# 3. Apply changes
terraform apply tfplan
```

#### **Phase 2: Verify Deployment** (10 minutes)
```bash
# 1. Check ALB status
aws elbv2 describe-load-balancers \
  --names neobotnet-v2-dev-alb \
  --region us-east-1 \
  --query 'LoadBalancers[0].{State:State.Code,DNS:DNSName}'

# Expected: State=active, DNS=neobotnet-v2-dev-alb-*.elb.amazonaws.com

# 2. Check target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --names neobotnet-v2-dev-tg \
    --region us-east-1 \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text) \
  --region us-east-1

# Expected: TargetHealth.State=healthy

# 3. Test ALB directly
ALB_DNS=$(aws elbv2 describe-load-balancers \
  --names neobotnet-v2-dev-alb \
  --region us-east-1 \
  --query 'LoadBalancers[0].DNSName' \
  --output text)

curl -v http://$ALB_DNS/health
# Expected: HTTP 200, {"status":"healthy"}

# 4. Test via CloudFront (wait ~5 min for cache invalidation)
sleep 300
curl -v https://aldous-api.neobotnet.com/health
# Expected: HTTP 200, {"status":"healthy"}
```

#### **Phase 3: Update GitHub Actions** (5 minutes)
```bash
# Remove DNS update step from workflow
git checkout dev
# Edit .github/workflows/deploy-backend-optimized-improved.yml
git add .github/workflows/deploy-backend-optimized-improved.yml
git commit -m "infra: remove DNS update step (ALB handles routing)"
git push origin dev
```

---

## **🔍 Testing & Validation**

### **Test 1: Health Check**
```bash
# Via ALB
curl http://$ALB_DNS/health

# Via CloudFront
curl https://aldous-api.neobotnet.com/health

# Expected: Both return 200 OK
```

### **Test 2: Scan Trigger**
```bash
# Login and trigger scan
curl -X POST https://aldous-api.neobotnet.com/api/v1/scans \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "assets": {
      "17e70cea-9abd-4d4d-a71b-daa183e9b2de": {
        "modules": ["subfinder"],
        "active_domains_only": true
      }
    }
  }'

# Expected: Returns scan_id immediately, no 502 errors
```

### **Test 3: Deployment Resilience**
```bash
# Trigger a new deployment
git commit --allow-empty -m "test: trigger deployment"
git push origin dev

# Monitor during deployment
while true; do
  curl -s -o /dev/null -w "%{http_code}\n" https://aldous-api.neobotnet.com/health
  sleep 2
done

# Expected: Continuous 200 responses (no 502/503)
```

### **Test 4: Multiple Requests (Load)**
```bash
# Stress test with 10 concurrent requests
for i in {1..10}; do
  curl -s https://aldous-api.neobotnet.com/health &
done
wait

# Expected: All return 200 OK
```

---

## **🔄 Rollback Plan**

If issues arise, revert to direct ECS access:

```bash
cd infrastructure/terraform

# 1. Revert Terraform changes
git revert <commit-hash>

# 2. Re-apply old configuration
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 3. Restore DNS update in GitHub Actions
git revert <github-actions-commit>
git push origin dev
```

**Estimated Rollback Time**: 20 minutes

---

## **📊 Success Metrics**

### **Before ALB (Current State)**
- ❌ 502 errors during deployments: ~3-5 occurrences per deploy
- ❌ Downtime during task restart: ~30-60 seconds
- ❌ Manual DNS management: Required for every deployment
- ❌ Single point of failure: 1 task crash = downtime
- ⚠️ Health checks: None

### **After ALB (Target State)**
- ✅ 502 errors during deployments: 0 (zero-downtime)
- ✅ Downtime during task restart: 0 seconds (rolling deployment)
- ✅ Manual DNS management: None (ALB DNS is stable)
- ✅ Redundancy: 2+ tasks, automatic failover
- ✅ Health checks: Every 30s, automatic unhealthy task removal

---

## **💰 Cost Analysis**

### **New Monthly Costs**
| Resource | Cost | Calculation |
|----------|------|-------------|
| **ALB** | $16.20 | $0.0225/hour × 720 hours |
| **LCU** | $7.20 | $0.008/LCU-hour × 30 LCU-hours/day × 30 days |
| **Optional: 2nd ECS Task** | $50.40 | 0.5 vCPU + 1GB RAM × $0.07/hour × 720 hours |
| **Total (without 2nd task)** | **$23.40/mo** | |
| **Total (with 2nd task)** | **$73.80/mo** | |

### **Value Justification**
- **Reliability**: Eliminates production outages
- **Developer Time**: Saves ~2 hours/month debugging 502s
- **User Experience**: No downtime during deployments
- **Scalability**: Enables future horizontal scaling
- **Industry Standard**: Required for any production service

**ROI**: $23/month is negligible compared to downtime costs and developer time.

---

## **📝 Notes & Considerations**

### **Why Not Use NAT Gateway?**
- NAT Gateway costs ~$33/month per AZ
- Current architecture uses public IPs for internet access (works fine)
- Redis is in private subnets (doesn't need NAT)
- **Decision**: Keep current setup, ALB provides needed reliability

### **Why 2 Tasks Instead of 1?**
- **With 1 task**: ALB still eliminates DNS issues, but no redundancy
- **With 2 tasks**: Zero-downtime rolling deployments
- **Recommendation**: Start with 1, increase to 2 after testing

### **HTTPS Termination**
- CloudFront handles HTTPS termination (has SSL cert)
- ALB only needs HTTP listener
- If direct ALB access needed, add HTTPS listener + ACM cert

### **WebSocket Support**
- ALB supports WebSockets natively
- No additional configuration needed
- Future enhancement: Real-time scan progress via WS

---

## **🎯 Timeline & Effort**

| Phase | Tasks | Estimated Time | Actual Time |
|-------|-------|----------------|-------------|
| **Planning** | Document analysis, plan creation | 2 hours | - |
| **Implementation** | Terraform changes (5 steps) | 30 minutes | - |
| **Testing** | Local testing, validation | 20 minutes | - |
| **Deployment** | Apply Terraform, verify | 30 minutes | - |
| **Monitoring** | Post-deployment observation | 1 hour | - |
| **Documentation** | Update docs, runbooks | 30 minutes | - |
| **Total** | | **4.5 hours** | - |

---

**Status**: ⏸️ READY FOR APPROVAL  
**Next Action**: Review plan with user, get approval to proceed  
**Risk Level**: 🟢 LOW (rollback plan available, minimal changes)
