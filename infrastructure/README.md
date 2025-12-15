# 🚀 NeoBot-Net v2 Infrastructure

**Unified deployment approach for consistent CI/CD and local development**

## 🎯 Quick Start

### First Time Setup

1. **Copy the configuration template:**
```bash
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
```

2. **Fill in your actual secrets in `terraform.tfvars`:**
```hcl
supabase_url              = "https://your-actual-project.supabase.co"
supabase_anon_key         = "your-actual-anon-key"
supabase_service_role_key = "your-actual-service-role-key"
jwt_secret_key            = "your-actual-jwt-secret"
```

3. **Make scripts executable:**
```bash
chmod +x scripts/*.sh
```

### Unified Deployment

```bash
cd infrastructure/terraform
../scripts/deploy-local.sh
```

This script mirrors the GitHub Actions workflow and ensures consistency.

## 🔧 Problem Solutions

### Issue 1: Environment Variables Mismatch ✅ FIXED

**Problem**: Different variable sources between CI/CD and local
- **GitHub Actions**: Uses secrets via `TF_VAR_*` 
- **Local**: Used `terraform.tfvars` with placeholders

**Solution**: 
- Created `terraform.tfvars.example` template
- Local `terraform.tfvars` now contains real secrets (git-ignored)
- Both CI/CD and local use same actual values

### Issue 2: Dynamic IP Management ✅ FIXED

**Problem**: DNS updates handled differently in CI vs local
- **GitHub Actions**: Manual DNS updates outside Terraform
- **Local**: Unreliable `data.external` resource

**Solution**:
- Removed problematic `data.external.current_ecs_ip`
- Local deployment script now mirrors GitHub Actions logic
- Consistent DNS management in both environments

## 📁 File Structure

```
infrastructure/
├── terraform/
│   ├── *.tf                    # Terraform configuration
│   ├── terraform.tfvars        # Local secrets (git-ignored)
│   ├── terraform.tfvars.example # Template
│   └── .gitignore              # Protects secrets
├── scripts/
│   ├── deploy-local.sh         # Unified deployment script
│   └── get-current-ip.sh       # IP debugging utility
└── README.md                   # This file
```

## 🛠️ Utility Scripts

### Full Deployment
```bash
./scripts/deploy-local.sh
```
- Validates environment and secrets
- Runs Terraform with current ECS IP
- Updates DNS records automatically
- Performs health checks
- **Mirrors GitHub Actions workflow exactly**

### Check Current IP
```bash
./scripts/get-current-ip.sh
```
- Shows current ECS task IP
- Compares with DNS record
- Provides manual update commands if needed

### Update ECS IP (New!)
```bash
./scripts/update-ecs-ip.sh
```
- **Automatically updates DNS when ECS IP changes**
- Gets current ECS task IP
- Updates Route53 DNS record if needed
- Clears CloudFront cache automatically
- Tests backend health
- **Perfect for cost-optimized architecture without load balancer**

## 🌐 Architecture

### Domain Setup
- **HTTPS API**: `https://aldous-api.neobotnet.com` (via CloudFront)
- **Direct API**: `http://<ecs-ip>:8000` (for development)
- **DNS Bridge**: `ecs-direct.aldous-api.neobotnet.com` → ECS IP

### Flow
```
Internet → CloudFront → ecs-direct.aldous-api.neobotnet.com → ECS Task IP
```

## 🔍 Troubleshooting

### "Placeholder values found" Error
```bash
# Fix: Edit terraform.tfvars with real secrets
nano terraform.tfvars
# Replace all "your-*" placeholders with actual values
```

### "DNS needs update" Warning
```bash
# Quick fix:
./scripts/get-current-ip.sh
# Follow the manual update command shown
```

### Hanging Curl Requests
```bash
# Check if IP changed:
./scripts/get-current-ip.sh

# Update DNS and redeploy:
./scripts/deploy-local.sh
```

## 🔐 Security Notes

- `terraform.tfvars` is git-ignored and contains real secrets
- Never commit actual secrets to the repository
- GitHub Actions uses repository secrets
- AWS credentials should be configured via AWS CLI profiles

## 🚀 Benefits

### Before (Issues)
- ❌ Environment variable conflicts
- ❌ Inconsistent deployments
- ❌ Manual DNS troubleshooting
- ❌ Different CI/CD vs local logic

### After (Fixed)
- ✅ Unified variable management
- ✅ Consistent CI/CD and local deployments  
- ✅ Automatic DNS updates
- ✅ Same logic everywhere
- ✅ Better debugging tools

## 📊 Deployment Comparison

| Aspect | GitHub Actions | Local (Before) | Local (After) |
|--------|----------------|----------------|---------------|
| Variables | Repository secrets | Placeholders | Real secrets |
| DNS Updates | Automatic | Manual | Automatic |
| IP Detection | Runtime logic | External data | Runtime logic |
| Consistency | ✅ | ❌ | ✅ |

Your deployment is now **production-ready and developer-friendly**! 🎉
