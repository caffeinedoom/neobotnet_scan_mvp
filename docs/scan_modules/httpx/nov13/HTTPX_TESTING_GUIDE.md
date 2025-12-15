# HTTPx Testing Guide

**Status**: Ready for Phase 4 Testing  
**Date**: 2025-11-14  
**Deployment**: Awaiting GitHub Actions build

---

## 🎯 Quick Start (Once Deployed)

### **Test HTTPx with Subfinder Pipeline**

```bash
# 1. Set your password
export SCAN_TEST_PASSWORD="TestSamPluck2025!!"

# 2. Test subfinder → httpx (recommended for first test)
./docs/test_scan.sh \
  --asset-id 6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e \
  --modules '["subfinder", "httpx"]'
```

**Expected Duration**: 1-2 minutes for EpicGames asset

---

## 📋 Test Scenarios

### **Scenario 1: HTTPx Only** (Fastest)
Tests httpx consumer reading from subfinder's stream.

```bash
./docs/test_scan.sh -a <asset-id> -m '["subfinder", "httpx"]'
```

**What to verify:**
- ✅ Scan completes successfully
- ✅ HTTPx container launches in ECS
- ✅ HTTP probes are inserted to database
- ✅ No errors in CloudWatch logs

---

### **Scenario 2: All Three Modules** (Full Pipeline)
Tests complete pipeline: subfinder → dnsx + httpx (parallel)

```bash
./docs/test_scan.sh -a <asset-id> -m '["subfinder", "dnsx", "httpx"]'
```

**What to verify:**
- ✅ Both dnsx and httpx consume from same stream
- ✅ No Redis Stream conflicts
- ✅ Both modules complete successfully
- ✅ Database has both dns_records AND http_probes

---

### **Scenario 3: Existing Asset Re-scan**
Tests httpx on an asset already scanned (has subdomains).

```bash
# Use asset that was previously scanned with subfinder
./docs/test_scan.sh -a <existing-asset-id> -m '["subfinder", "httpx"]'
```

**What to verify:**
- ✅ HTTPx probes existing subdomains
- ✅ No duplicate subdomains created
- ✅ New http_probes entries created

---

## 🔍 Expected Test Output

### **1. Scan Trigger Response**
```json
{
  "scan_id": "632faf54-7c76-454f-a16b-dd6e405a6a49",
  "status": "pending",
  "assets_count": 1,
  "total_domains": 2,
  "streaming_assets": 1,
  "response_time": "1-2s"
}
```

### **2. CloudWatch Logs (Success)**
```
[632faf54] 🚀 PHASE 3: Launching background execution
[632faf54] 🌊 HTTPx Streaming Consumer Mode
[632faf54] 🔍 Starting to consume subdomains from stream...
[632faf54] 🌐 Probing: account.epicgames.com (from subfinder)
[632faf54]   ✅ Found 2 HTTP probe(s)
[632faf54]      → https: 200 https://account.epicgames.com
[632faf54]      → http: 301 http://account.epicgames.com
[632faf54]   💾 HTTP probes: 2 inserted, 0 skipped, 0 errors
[632faf54] 🏁 Completion marker detected!
[632faf54] ✅ HTTPx streaming consumer completed successfully
```

### **3. Final Status**
```
Test Configuration:
  Asset ID:         6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e
  Scan ID:          632faf54-7c76-454f-a16b-dd6e405a6a49
  Modules:          subfinder, httpx

Results:
  Final Status:     completed
  Total Duration:   93s (~1m 33s)
  Completed Assets: 1/1
  Failed Assets:    0

✅ TEST PASSED ✅
```

---

## 🗄️ Database Verification

After a successful scan, verify data in Supabase:

### **Check HTTP Probes Count**
```sql
SELECT COUNT(*) 
FROM http_probes 
WHERE scan_job_id IN (
  SELECT id FROM asset_scan_jobs 
  WHERE scan_id = '<scan_id>'
);
```

### **View HTTP Probe Details**
```sql
SELECT 
  subdomain,
  status_code,
  url,
  title,
  webserver,
  technologies,
  cdn_name,
  scheme,
  port
FROM http_probes 
WHERE scan_job_id IN (
  SELECT id FROM asset_scan_jobs 
  WHERE scan_id = '<scan_id>'
)
ORDER BY created_at DESC
LIMIT 10;
```

### **Check for Expected Fields**
```sql
-- Verify all 14 fields are populated
SELECT 
  COUNT(*) FILTER (WHERE status_code IS NOT NULL) as has_status,
  COUNT(*) FILTER (WHERE title IS NOT NULL) as has_title,
  COUNT(*) FILTER (WHERE webserver IS NOT NULL) as has_webserver,
  COUNT(*) FILTER (WHERE technologies != '[]') as has_tech,
  COUNT(*) FILTER (WHERE cdn_name IS NOT NULL) as has_cdn,
  COUNT(*) as total
FROM http_probes 
WHERE scan_job_id IN (
  SELECT id FROM asset_scan_jobs 
  WHERE scan_id = '<scan_id>'
);
```

---

## 🐛 Troubleshooting

### **Error: "httpx module not found"**
```
❌ HTTP 400: Invalid module: httpx
```

**Cause**: Module not yet registered or inactive  
**Solution**: Check `scan_module_profiles` table:
```sql
SELECT module_name, is_active 
FROM scan_module_profiles 
WHERE module_name = 'httpx';
```

If `is_active = false`, activate it:
```sql
UPDATE scan_module_profiles 
SET is_active = true 
WHERE module_name = 'httpx';
```

---

### **Error: "httpx task failed to start"**
```
ECS Task failed: ResourceInitializationError
```

**Cause**: Docker image not in ECR or task definition missing  
**Check**:
1. GitHub Actions build succeeded
2. ECR has `neobotnet-v2-dev-httpx-batch:latest`
3. Task definition `neobotnet-v2-dev-httpx-batch` exists

**AWS CLI Check**:
```bash
# Check ECR image
aws ecr describe-images \
  --repository-name neobotnet-v2-dev-httpx-batch \
  --region us-east-1

# Check task definition
aws ecs describe-task-definition \
  --task-definition neobotnet-v2-dev-httpx-batch \
  --region us-east-1
```

---

### **No HTTP Probes in Database**
```
✅ Scan completed but http_probes table is empty
```

**Possible Causes**:
1. **Subdomains have no web service** (all offline)
2. **HTTPx container crashed** (check logs)
3. **Database permissions** (RLS policy issue)

**Debug**:
```bash
# Check CloudWatch for httpx container
aws logs tail /ecs/neobotnet-v2-dev-httpx-batch --follow

# Check if subdomains were found
SELECT COUNT(*) FROM subdomains 
WHERE scan_job_id IN (
  SELECT id FROM asset_scan_jobs WHERE scan_id = '<scan_id>'
);

# Test RLS policy
-- Login as your user and query:
SELECT * FROM http_probes LIMIT 1;
```

---

### **CloudWatch Logs Not Found**
```
⚠️  No logs found for correlation ID: [632faf54]
```

**Solutions**:
1. Wait 30-60 seconds for logs to propagate
2. Check correct log group:
   - Generic: `/aws/ecs/neobotnet-v2-dev`
   - HTTPx specific: `/ecs/neobotnet-v2-dev-httpx-batch`
3. Verify AWS CLI credentials

**Manual CloudWatch Check**:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/neobotnet-v2-dev-httpx-batch \
  --start-time $(date -d '30 minutes ago' +%s)000 \
  --filter-pattern "<scan_id_short>" \
  --region us-east-1
```

---

## 📊 Success Criteria

**For a passing test, verify ALL of these:**

✅ **API Response**
- [ ] Scan triggered with `status: "pending"`
- [ ] Response time < 3 seconds (non-blocking)
- [ ] `streaming_assets: 1`

✅ **ECS Task**
- [ ] HTTPx task launched in ECS cluster
- [ ] Task status: `RUNNING` → `STOPPED` (success)
- [ ] Exit code: 0

✅ **CloudWatch Logs**
- [ ] "HTTPx Streaming Consumer Mode" appears
- [ ] "Starting to consume subdomains from stream" appears
- [ ] "HTTP probes: X inserted" appears (X > 0)
- [ ] "✅ HTTPx streaming consumer completed successfully" appears
- [ ] No ERROR or Exception messages

✅ **Database**
- [ ] `http_probes` table has new entries
- [ ] `scan_job_id` matches the scan
- [ ] All 14 fields populated (status, title, tech, etc.)
- [ ] JSONB fields valid (`technologies`, `chain_status_codes`)
- [ ] Foreign keys valid (no orphaned records)

✅ **Final Status**
- [ ] Scan status: `completed`
- [ ] Failed assets: 0
- [ ] Test duration: < 3 minutes

---

## 🎯 Post-Deployment Checklist

Before declaring HTTPx production-ready:

**Phase 4: Local Testing**
- [x] Docker build successful (116MB image)
- [x] Go binary compiles (55MB, 0 errors)
- [ ] Test simple mode locally
- [ ] Test streaming mode with docker-compose

**Phase 5: Cloud Testing** (CURRENT)
- [ ] GitHub Actions build succeeds
- [ ] ECR image pushed successfully
- [ ] ECS task definition created
- [ ] Module registered in database
- [ ] Test scan with httpx completes
- [ ] HTTP probes inserted correctly

**Phase 6: Activation**
- [ ] Set `is_active = true` in scan_module_profiles
- [ ] Update frontend to show httpx option
- [ ] Add httpx to default module selection

**Phase 7: Monitoring**
- [ ] CloudWatch alarms configured
- [ ] Dashboard shows httpx metrics
- [ ] Alert on httpx failures

---

## 📞 Quick Reference Commands

```bash
# Test httpx
export SCAN_TEST_PASSWORD="TestSamPluck2025!!"
./docs/test_scan.sh -a 6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e -m '["subfinder", "httpx"]'

# Check CloudWatch (live tail)
aws logs tail /ecs/neobotnet-v2-dev-httpx-batch --follow

# Count HTTP probes
psql -h <supabase-host> -U postgres -d postgres -c \
  "SELECT COUNT(*) FROM http_probes WHERE asset_id = '<asset-id>';"

# Check module status
psql -h <supabase-host> -U postgres -d postgres -c \
  "SELECT * FROM scan_module_profiles WHERE module_name = 'httpx';"

# Activate httpx
psql -h <supabase-host> -U postgres -d postgres -c \
  "UPDATE scan_module_profiles SET is_active = true WHERE module_name = 'httpx';"
```

---

**Ready to test once GitHub Actions completes! 🚀**

**Next**: Wait for deployment, then run first test with `["subfinder", "httpx"]`

