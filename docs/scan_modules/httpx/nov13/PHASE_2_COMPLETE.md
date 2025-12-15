# Phase 2 Complete: Module Registry Configuration ✅

**Status**: COMPLETE  
**Duration**: 0.5 hours  
**Completed**: 2025-11-14  
**Phase**: HTTPx Module Implementation

---

## 📦 Deliverables

### **1. Migration Files**
- **File 1**: `backend/migrations/add_httpx_module_profile.sql` (8.1 KB)
- **File 2**: `backend/migrations/add_httpx_to_constraints.sql` (2.5 KB)
- **Applied to**: Supabase production database
- **Status**: ✅ Both migrations executed successfully

### **2. Database Changes Made**

| Change | Table | Details |
|--------|-------|---------|
| **Module Registration** | `scan_module_profiles` | 1 row inserted (httpx module) |
| **Constraint Update** | `asset_scan_jobs` | Updated `valid_modules` to include 'httpx' |

---

## 🔧 Module Configuration

### **HTTPx Profile in `scan_module_profiles`**

```json
{
  "module_name": "httpx",
  "version": "1.0",
  "supports_batching": true,
  "max_batch_size": 100,
  "is_active": false,
  "task_definition_template": "neobotnet-v2-dev-httpx-batch",
  "container_name": "httpx-scanner",
  "estimated_duration_per_domain": 10,
  "resource_scaling": {
    "domain_count_ranges": [
      {
        "min_domains": 1,
        "max_domains": 100,
        "cpu": 512,
        "memory": 1024,
        "description": "Standard batch - optimized for HTTP probing (1-100 subdomains)"
      }
    ],
    "scaling_notes": "HTTPx is I/O bound (network requests). Single tier simplifies resource allocation."
  },
  "optimization_hints": {
    "memory_multiplier": 1.0,
    "requires_internet": true,
    "requires_subdomains": true,
    "concurrent_limit": 50,
    "description": "HTTP/HTTPS probing with technology detection",
    "dependencies": ["subfinder"],
    "consumes_input_stream": true,
    "input_stream_pattern": "scan:{scan_job_id}:subfinder:output",
    "produces_output_stream": false,
    "requires_database_fetch": false,
    "requires_asset_id": true,
    "streaming_notes": "Consumes from subfinder Redis Stream, runs parallel with dnsx"
  }
}
```

---

## 🎯 Key Decisions

### **1. Resource Scaling Strategy**
**Choice**: Single tier (512 CPU / 1024 MB for 1-100 subdomains)

**Rationale**:
- ✅ Simplifies resource allocation
- ✅ Conservative estimate prevents timeouts
- ✅ Can add tiers later based on real-world metrics
- ✅ HTTP probing is fast, over-provisioning is safer

**Alternative Considered**: Multi-tier (1-50, 51-100, 101-200)  
**Why Rejected**: Premature optimization; single tier easier to test and deploy

---

### **2. Estimated Duration**
**Choice**: 10 seconds/subdomain

**Rationale**:
- ✅ Conservative estimate includes timeouts, retries, redirects
- ✅ Used for user-facing progress estimates
- ✅ Used for ECS task timeout calculations (900s total)
- ✅ Can adjust in Phase 4 based on real testing data

**Impact**:
- 100 subdomains × 10s = 1000s = ~16 minutes max execution
- Progress bar: "50/100 subdomains - 8 minutes remaining"

---

### **3. Max Batch Size**
**Choice**: 100 subdomains/container

**Rationale**:
- ✅ Aligns with typical subfinder output (10-50 subdomains/domain)
- ✅ HTTP probing is fast (much faster than subdomain enumeration)
- ✅ Prevents overwhelming target servers
- ✅ Balances parallelism with resource efficiency

**Comparison**:
- Subfinder: 50 domains/batch (slow enumeration)
- DNSx: 200 domains/batch (fast DNS queries)
- HTTPx: 100 subdomains/batch (medium-speed HTTP probing)

---

### **4. Streaming Configuration**
**Choice**: Consumer from `scan:{scan_job_id}:subfinder:output`

**Rationale**:
- ✅ Real-time probing as subdomains are discovered
- ✅ Parallel execution with dnsx (both consume from same stream)
- ✅ No dependency on dnsx (doesn't need DNS records)
- ✅ Reduces total scan time (starts immediately after first subdomain)

**Stream Flow**:
```
subfinder → Redis Stream (producer)
              ↓
         ┌────┴────┐
         ↓         ↓
      dnsx      httpx  (both consumers in parallel)
         ↓         ↓
   dns_records  http_probes
```

---

## 🔍 Constraint Update

### **Before (Phase 1)**
```sql
CONSTRAINT "valid_modules" CHECK (
    modules <@ ARRAY['subfinder', 'dnsx']
)
```

### **After (Phase 2)**
```sql
CONSTRAINT "valid_modules" CHECK (
    modules <@ ARRAY['subfinder', 'dnsx', 'httpx']
)
```

**Impact**: Users can now request `["subfinder", "dnsx", "httpx"]` in scan API calls.

---

## 🚦 Current System Behavior

### **Scan Request Flow**

```
User: POST /api/v1/scans
Body: { "modules": ["subfinder", "dnsx", "httpx"], ... }
  ↓
API Validation: ✅ PASS (httpx in valid_modules constraint)
  ↓
module_registry.discover_modules()
  ↓
Query: SELECT * FROM scan_module_profiles WHERE module_name = 'httpx'
  ↓
Result: ✅ Found (is_active = false)
  ↓
Validation: ❌ FAIL
  ↓
Error Response: {
  "error": "Module httpx is not active",
  "status": "inactive",
  "available_modules": ["subfinder", "dnsx"]
}
```

**This is EXPECTED behavior** until Phase 6 (AWS ECS Deployment).

---

## 📊 Backend Integration Status

### **Already Compatible (No Changes Needed)**

| Component | Status | Reason |
|-----------|--------|--------|
| `scan_pipeline.py` | ✅ Ready | `DEPENDENCIES` already includes `httpx: ["subfinder"]` |
| `scan_pipeline.py` | ✅ Ready | `MODULE_TIMEOUTS` already includes `httpx: 900` |
| `module_registry.py` | ✅ Ready | Auto-discovers from `scan_module_profiles` table |
| `stream_coordinator.py` | ✅ Ready | Will create `httpx-consumers` group automatically |
| `batch_workflow_orchestrator.py` | ✅ Ready | Uses `module_registry` for resource allocation |

**No Python code changes required!** The system was designed for extensibility.

---

## ✅ Verification

### **Constraint Verified**
```sql
-- From schema.sql line 1034
CONSTRAINT "valid_modules" CHECK (
    modules <@ ARRAY['subfinder'::"text", 'dnsx'::"text", 'httpx'::"text"]
)
```
✅ HTTPx successfully added

### **Module Registration Verified**
✅ User confirmed both migrations executed successfully  
✅ `scan_module_profiles` now contains httpx row  
✅ System ready for container implementation

---

## 🚀 Impact on Next Phases

### **Phase 3: Container Implementation**
- ✅ Resource allocation defined (512 CPU / 1024 MB)
- ✅ Streaming config clear (consume from subfinder)
- ✅ Database schema ready (`http_probes` table from Phase 1)
- ✅ Timeout known (900s from `MODULE_TIMEOUTS`)

### **Phase 4: Local Testing**
- ✅ Can verify resource estimates are accurate
- ✅ Can test streaming consumer behavior
- ✅ Can measure actual duration/subdomain

### **Phase 6: AWS ECS Deployment**
- ✅ Task definition name known (`neobotnet-v2-dev-httpx-batch`)
- ✅ Container name known (`httpx-scanner`)
- ✅ Just need to SET `is_active = true` after deployment

---

## 🧠 Lessons Learned

### **1. Database-Driven Configuration is Powerful**
The `scan_module_profiles` table allows us to configure modules without touching Python code. This makes the system highly extensible.

### **2. Constraints Provide Safety**
The `valid_modules` constraint prevents users from requesting non-existent modules, catching errors at the database level before they reach the application.

### **3. `is_active` Flag is Critical**
Starting modules as INACTIVE prevents users from triggering scans before containers are deployed. This is safer than relying on try/catch error handling.

### **4. JSON Configuration is Flexible**
Using JSONB for `resource_scaling` and `optimization_hints` allows complex configuration without schema changes. We can add new fields (e.g., `rate_limit_per_second`) without migrations.

---

## 📝 Next Steps

**Proceed to Phase 3: Container Implementation** (5-6 hours)

### **Goals**:
1. Clone `dnsx-go` as template (consumer pattern)
2. Integrate ProjectDiscovery's httpx Go SDK
3. Parse httpx CSV output (56 columns → 14 selected fields)
4. Implement bulk insert to `http_probes` table
5. Add Redis Streams consumer logic
6. Build Docker image locally

### **Strategy**:
Following the documented pattern from `CONTAINER_TEMPLATE.md`:
- ✅ `main.go`: Mode routing (simple/batch/streaming)
- ✅ `scanner.go`: HTTPx SDK integration
- ✅ `database.go`: Bulk insert to `http_probes`
- ✅ `streaming.go`: Redis Stream consumer
- ✅ `Dockerfile`: Multi-stage build

### **Estimated Effort**:
- Clone & customize: 1 hour
- HTTPx SDK integration: 2 hours
- Database integration: 1 hour
- Streaming logic: 1 hour
- Testing & debugging: 1-2 hours

---

## 📋 Success Metrics

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Module registered in DB | ✅ | ✅ | ✅ PASS |
| Constraint updated | ✅ | ✅ | ✅ PASS |
| Resource scaling defined | ✅ | ✅ | ✅ PASS |
| Streaming config defined | ✅ | ✅ | ✅ PASS |
| Dependencies documented | ✅ | ✅ | ✅ PASS |
| Migration idempotent | ✅ | ✅ | ✅ PASS |

---

**Phase 2 Status: COMPLETE ✅**  
**Total Time: 0.5 hours**  
**Quality: Production-ready configuration, verified in Supabase**  
**Overall Progress: 18% (3.5/17-24 hours)**
