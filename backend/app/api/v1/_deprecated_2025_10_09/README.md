# Deprecated Code - Archived October 9, 2025

This directory contains code deprecated during the unified architecture migration.

---

## 📁 What Was Removed

**File**: `recon.py` (449 lines)

**Endpoints Removed**:
- `POST /api/v1/recon/subdomain/scan` - Individual domain scanning
- `GET /api/v1/recon/subdomain/scan/{job_id}` - Job status
- `GET /api/v1/recon/subdomain/scan/{job_id}/subdomains` - Results
- `GET /api/v1/recon/subdomain/scan/{job_id}/progress` - Progress
- `GET /api/v1/recon/subdomain/scan/{job_id}/errors` - Errors
- `GET /api/v1/recon/subdomain/scan/{job_id}/stream` - Stream
- `GET /api/v1/recon/jobs` - List jobs

---

## ❓ Why Removed

### **Technical Reasons**:
1. **Dual Path Complexity**: Maintained two separate scan paths (individual vs asset-level)
2. **No Batch Optimization**: Individual scans couldn't leverage batch processing
3. **Higher Costs**: Each domain launched separate ECS tasks (40% more expensive)
4. **Harder Maintenance**: Dual codebase for same functionality
5. **Confusion**: Users didn't know which endpoint to use

### **Architecture Benefits** (New System):
- ✅ **Unified**: Single scan path through asset-level API
- ✅ **Optimized**: Batch processing with cross-asset optimization
- ✅ **Cost Efficient**: 40% cost reduction through intelligent batching
- ✅ **Better UX**: Asset-centric interface more intuitive
- ✅ **Scalable**: Template-based module system

---

## 🔄 Migration Path

### **Old Approach** (Deprecated):
```bash
POST /api/v1/recon/subdomain/scan
{
  "domain": "example.com",
  "modules": ["subfinder"]
}
```

### **New Approach** (Current):
```bash
# 1. Create asset (if needed)
POST /api/v1/assets
{
  "name": "Example Company",
  "description": "Target asset"
}

# 2. Add domain to asset
POST /api/v1/assets/{asset_id}/domains
{
  "domain": "example.com"
}

# 3. Scan entire asset
POST /api/v1/assets/{asset_id}/scan
{
  "modules": ["subfinder"],
  "enable_batch_optimization": true
}
```

---

## 📊 Verification

**Phase 1 Verification** (October 9, 2025):
- ✅ Deployed deprecation logging to production
- ✅ Monitored for 24+ hours
- ✅ Zero usage detected of `/recon` endpoints
- ✅ All production scans using `/assets` API
- ✅ Scan completed successfully: 47 domains, 1,040 subdomains

**Conclusion**: Safe to archive (confirmed unused in production)

---

## 📚 Related Documentation

- See `INFRASTRUCTURE_ANALYSIS.md` for detailed analysis
- See `TECHNICAL_DEBT_ANALYSIS.md` for cleanup rationale
- See `CLEANUP_IMPLEMENTATION_GUIDE.md` for implementation steps

---

## 🔙 Rollback (If Needed)

If endpoints need to be restored:

```bash
# Move file back
git mv backend/app/api/v1/_deprecated_2025_10_09/recon.py \
       backend/app/api/v1/

# Restore import in main.py
# Add: from .api.v1.recon import router as recon_router
# Add: app.include_router(recon_router, prefix=settings.api_v1_str)

# Commit and deploy
git commit -m "Rollback: Restore /recon endpoints"
git push origin dev
```

---

**Archived**: October 9, 2025  
**Verified Unused**: Yes (Phase 1 logging confirmed zero usage)  
**Safe to Delete**: After 90 days (January 2026)
