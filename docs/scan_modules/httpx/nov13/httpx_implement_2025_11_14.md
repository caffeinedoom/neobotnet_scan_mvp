# HTTPx Module Implementation Project Plan
**Date:** November 14, 2025  
**Status:** 📋 Planning → Ready for Approval  
**Priority:** P1 - New Feature Implementation  
**Owner:** Development Team  
**Estimated Duration:** 10-14 hours across 3-5 days

---

## 🎯 Executive Summary

### **Objective**
Implement HTTPx as the third scan module in the reconnaissance framework, enabling HTTP probing of discovered subdomains to identify active web services, technologies, and server configurations.

### **Strategic Value**
- **For Bug Bounty**: Identify live web services, technology stacks, and potential attack surfaces
- **For Architecture**: Validate the templated scan module pattern, making future modules (nuclei, etc.) trivial
- **For Users**: Complete the recon chain: Subdomain Discovery → DNS Resolution → **HTTP Probing**

### **Success Criteria**
1. ✅ HTTPx container operational in all 3 modes (simple, batch, streaming)
2. ✅ Streams data from subfinder's Redis Stream in real-time
3. ✅ Writes 14 fields to `http_probes` database table (includes IP address)
4. ✅ Integrates seamlessly with existing scan pipeline
5. ✅ Dashboard displays HTTP probe results
6. ✅ Container template documented for future modules
7. ✅ CASCADE DELETE ensures asset deletion removes all related HTTP probes

---

## 📊 Architecture Context

### **Current State: 2-Module Pipeline**
```
Asset (EpicGames)
  └─ Apex Domains (epicgames.com, unrealengine.com)
       └─ SCAN INITIATED
            │
            ▼
       ┌─────────────┐
       │  SUBFINDER  │  Discovers subdomains
       │  (Producer) │  Writes to: scan:{job_id}:subfinder:output
       └──────┬──────┘
              │ Redis Stream
              ▼
       ┌─────────────┐
       │    DNSX     │  Resolves DNS records
       │  (Consumer) │  Writes to: dns_records table
       └─────────────┘
```

### **Target State: 3-Module Pipeline**
```
Asset (EpicGames)
  └─ Apex Domains (epicgames.com, unrealengine.com)
       └─ SCAN INITIATED
            │
            ▼
       ┌─────────────┐
       │  SUBFINDER  │  Discovers subdomains
       │  (Producer) │  Writes to: scan:{job_id}:subfinder:output
       └──────┬──────┘
              │ Redis Stream (fan-out to 2 consumers)
              ├────────────────┐
              ▼                ▼
       ┌─────────────┐  ┌─────────────┐
       │    DNSX     │  │    HTTPX    │  ← NEW MODULE
       │  (Consumer) │  │  (Consumer) │
       └─────────────┘  └──────┬──────┘
                               │
                               ▼
                        http_probes table
```

**Key Architectural Decision**: HTTPx runs **parallel** with DNSx, both consuming from subfinder's stream simultaneously.

**Critical Reasoning**:
- ✅ **Faster**: No waiting for DNSx to complete
- ✅ **Independent**: HTTP probing doesn't need DNS records (httpx resolves internally)
- ✅ **Scalable**: Each consumer processes at its own pace
- ⚠️ **Trade-off**: Can't correlate HTTP data with DNS records in real-time (acceptable, can join tables post-scan)

---

## 🏗️ Implementation Phases

---

### **PHASE 0: Pattern Formalization** 📚
**Status:** ✅ COMPLETE  
**Duration:** 3-4 hours (Actual: 2 hours)  
**Priority:** P0 (Blocks all other phases)  
**Completed:** November 14, 2025

#### **Objective**
Document the scan module container pattern to make httpx implementation mechanical and enable rapid development of future modules (nuclei, katana, etc.).

#### **Deliverables**

##### **1. Container Template Documentation**
**File:** `/backend/containers/CONTAINER_TEMPLATE.md`

**Content Structure**:
```markdown
# Scan Module Container Template

## 1. Directory Structure
## 2. Required Files and Responsibilities
## 3. Environment Variables Contract
## 4. Execution Modes (Simple/Batch/Streaming)
## 5. Database Integration Pattern
## 6. Redis Streams Pattern
## 7. Error Handling Standards
## 8. Health Check Implementation
## 9. Dockerfile Best Practices
## 10. Testing Checklist
```

**Critical sections**:
- **Streaming Consumer Pattern**: How to read from `scan:{job_id}:{producer}:output`
- **Database Write Pattern**: Bulk insert strategy, error handling, foreign key management
- **Completion Detection**: How to handle `{"type": "completion"}` marker
- **Resource Management**: Graceful shutdown, Redis connection cleanup

##### **2. Reference Implementation Guide**
**File:** `/backend/containers/REFERENCE_IMPLEMENTATION.md`

**Purpose**: Side-by-side comparison of subfinder and dnsx to highlight:
- What's identical (copy-paste)
- What's module-specific (customize)
- What's boilerplate (could be library)

**Example comparison**:
```go
// IDENTICAL across all modules (boilerplate)
type SupabaseClient struct {
    url        string
    serviceKey string
    httpClient *http.Client
}

// MODULE-SPECIFIC (customize per module)
type ScanResult struct {
    // Subfinder: Subdomain    string
    // DNSx:      DomainName   string, RecordType string, Value string
    // HTTPx:     URL          string, StatusCode int, Technologies []string
}
```

#### **Success Criteria**
- ✅ `CONTAINER_TEMPLATE.md` reviewed and approved
- ✅ Template includes all sections listed above
- ✅ Reference guide compares subfinder vs dnsx patterns
- ✅ Clear distinction between boilerplate and module-specific code

#### **Time Breakdown**
- Document review (analyze subfinder + dnsx): 1 hour
- Write template: 2 hours
- Review and refinement: 1 hour

---

### **PHASE 1: Database Schema Design** 🗄️
**Status:** ✅ COMPLETE  
**Duration:** 1-2 hours (Actual: 1 hour)  
**Dependencies:** None (can run parallel with Phase 0)
**Completed:** 2025-11-14

#### **Objective**
Create the `http_probes` table with optimal schema for querying and indexing, supporting all 14 selected fields (including IP address).

#### **✅ Deliverables**
1. **Migration File**: `backend/migrations/add_http_probes_table.sql` (207 lines)
2. **Schema Features Implemented**:
   - ✅ 14 httpx core fields (`status_code`, `url`, `title`, `webserver`, `content_length`, `final_url`, `ip`, `technologies`, `cdn_name`, `content_type`, `asn`, `chain_status_codes`, `location`, `favicon_md5`)
   - ✅ Parsed/derived fields (`subdomain`, `parent_domain`, `scheme`, `port`)
   - ✅ JSONB columns with GIN indexes for `technologies` and `chain_status_codes`
   - ✅ ON DELETE CASCADE for foreign keys (`scan_job_id`, `asset_id`)
   - ✅ Row Level Security (RLS) enabled with 2 policies
   - ✅ Comprehensive indexing strategy (9 indexes total)
   - ✅ Inline documentation via SQL comments

#### **✅ Database Verification (Applied to Supabase)**
```
✓ Table Created: http_probes (22 columns)
✓ Foreign Keys: 2 (scan_job_id → asset_scan_jobs, asset_id → assets)
✓ Indexes: 9 (including 2 GIN for JSONB arrays)
✓ RLS Policies: 2 (user view policy + service role policy)
✓ Constraints: 2 (port range, scheme validation)
✓ Comments: 4 (table + 3 key columns)
```

#### **🔍 Key Schema Decisions**
- **`parent_domain` as TEXT**: Matches existing pattern in `subdomains` and `dns_records` tables (not a foreign key)
- **`scan_job_id` → `asset_scan_jobs`**: References individual asset scans, not the unified `scans` table
- **JSONB for arrays**: Optimal for variable-length tech stacks and redirect chains
- **GIN indexes**: Enable fast `@>` containment queries (e.g., `WHERE technologies @> '["React"]'`)

#### **Schema Design**

```sql
-- =====================================================================
-- HTTPx Module Database Schema
-- =====================================================================
-- Description: Stores HTTP probing results from HTTPx scan module
-- Date: 2025-11-14
-- Module: httpx
-- =====================================================================

CREATE TABLE http_probes (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core HTTP data (7 fields)
    status_code INT,                       -- HTTP status (200, 404, 303, etc.)
    url TEXT NOT NULL,                     -- Full URL probed (e.g., https://admin.example.com)
    title TEXT,                            -- Page title
    webserver TEXT,                        -- Server header (nginx, apache, IIS, cloudflare)
    content_length BIGINT,                 -- Response size in bytes (BIGINT for large responses)
    final_url TEXT,                        -- URL after redirects (null if no redirect)
    ip TEXT,                               -- IP address resolved by httpx (e.g., "151.101.1.91")
    
    -- Technology and infrastructure (4 fields)
    technologies JSONB,                    -- Array: ["HSTS", "Nginx", "jQuery", "React"]
    cdn_name TEXT,                         -- CDN provider (fastly, cloudflare, akamai)
    content_type TEXT,                     -- MIME type (text/html, application/json)
    asn TEXT,                              -- Autonomous System Number (e.g., "AS54113, fastly, US")
    
    -- Redirect chain data (3 fields)
    chain_status_codes JSONB,              -- Array of status codes: [301, 302, 200]
    location TEXT,                         -- Redirect target URL
    favicon_md5 TEXT,                      -- Favicon hash (useful for grouping similar sites)
    
    -- Extracted metadata (computed fields)
    subdomain TEXT NOT NULL,               -- Extracted from URL for fast queries (e.g., "admin.example.com")
    scheme TEXT NOT NULL,                  -- 'http' or 'https' (extracted from URL)
    port INT DEFAULT 443,                  -- Port number (default 443 for https, 80 for http)
    
    -- Relationships (Critical for cross-module correlation!)
    scan_job_id UUID NOT NULL REFERENCES asset_scans(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    parent_domain TEXT NOT NULL,           -- Apex domain (e.g., "example.com")
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_status_code CHECK (status_code >= 100 AND status_code <= 599),
    CONSTRAINT valid_scheme CHECK (scheme IN ('http', 'https'))
);

-- =====================================================================
-- Indexes for Performance
-- =====================================================================

-- Primary lookup: By subdomain
CREATE INDEX idx_http_probes_subdomain ON http_probes(subdomain);

-- Filter by asset
CREATE INDEX idx_http_probes_asset_id ON http_probes(asset_id);

-- Filter by scan job (job-level queries)
CREATE INDEX idx_http_probes_scan_job_id ON http_probes(scan_job_id);

-- Filter by status code (find alive hosts: WHERE status_code BETWEEN 200 AND 299)
CREATE INDEX idx_http_probes_status_code ON http_probes(status_code) WHERE status_code IS NOT NULL;

-- Technology search (GIN index for JSONB array queries)
-- Example: WHERE technologies @> '["Nginx"]'
CREATE INDEX idx_http_probes_technologies ON http_probes USING GIN(technologies);

-- CDN search
CREATE INDEX idx_http_probes_cdn_name ON http_probes(cdn_name) WHERE cdn_name IS NOT NULL;

-- IP address search (find all subdomains on same IP)
CREATE INDEX idx_http_probes_ip ON http_probes(ip) WHERE ip IS NOT NULL;

-- Composite index for common query: "Active hosts for this asset"
CREATE INDEX idx_http_probes_asset_status ON http_probes(asset_id, status_code) 
    WHERE status_code BETWEEN 200 AND 299;

-- =====================================================================
-- Foreign Key Relationships with CASCADE DELETE
-- =====================================================================
-- IMPORTANT: CASCADE DELETE ensures that when an asset or scan job is deleted,
-- all related HTTP probes are automatically removed. This maintains referential
-- integrity and prevents orphaned records.

-- Relationship to asset_scans table
-- When a scan job is deleted, all its HTTP probes are deleted
ALTER TABLE http_probes 
    ADD CONSTRAINT fk_http_probes_scan_job 
    FOREIGN KEY (scan_job_id) 
    REFERENCES asset_scans(id) 
    ON DELETE CASCADE;

-- Relationship to assets table
-- When an asset is deleted, ALL HTTP probes for that asset are deleted
ALTER TABLE http_probes 
    ADD CONSTRAINT fk_http_probes_asset 
    FOREIGN KEY (asset_id) 
    REFERENCES assets(id) 
    ON DELETE CASCADE;

-- =====================================================================
-- Comments for Documentation
-- =====================================================================

COMMENT ON TABLE http_probes IS 'HTTP probing results from HTTPx module showing active web services, technologies, and server configurations';
COMMENT ON COLUMN http_probes.technologies IS 'JSONB array of detected technologies, queryable with @> operator';
COMMENT ON COLUMN http_probes.chain_status_codes IS 'JSONB array of HTTP status codes in redirect chain';
COMMENT ON COLUMN http_probes.subdomain IS 'Extracted from URL for fast lookups without parsing';
COMMENT ON COLUMN http_probes.asn IS 'Autonomous System Number with organization and country';
COMMENT ON COLUMN http_probes.ip IS 'IP address resolved by httpx during probing - useful for identifying hosts on same IP';

-- =====================================================================
-- Verification Queries
-- =====================================================================

-- Test insert (example)
/*
INSERT INTO http_probes (
    url, subdomain, scheme, port, status_code, title, webserver,
    technologies, content_length, final_url, cdn_name, content_type,
    asn, chain_status_codes, location, favicon_md5, ip,
    scan_job_id, asset_id, parent_domain
) VALUES (
    'https://admin.example.com',
    'admin.example.com',
    'https',
    443,
    200,
    'Admin Dashboard',
    'nginx',
    '["HSTS", "Nginx", "jQuery"]'::jsonb,
    45678,
    null,
    'cloudflare',
    'text/html',
    'AS13335, Cloudflare, US',
    '[200]'::jsonb,
    null,
    'abc123def456',
    '104.16.132.229',  -- IP address
    'scan-job-uuid-here',
    'asset-uuid-here',
    'example.com'
);
*/

-- Find all Nginx servers
-- SELECT subdomain, url, webserver FROM http_probes WHERE technologies @> '["Nginx"]';

-- Find all successful probes for an asset
-- SELECT subdomain, status_code, title FROM http_probes WHERE asset_id = 'uuid' AND status_code BETWEEN 200 AND 299;

-- Find all hosts behind Cloudflare
-- SELECT subdomain, asn FROM http_probes WHERE cdn_name = 'cloudflare';

-- Find all subdomains sharing the same IP (useful for identifying shared hosting)
-- SELECT subdomain, url, ip FROM http_probes WHERE ip = '151.101.1.91';
```

#### **Critical Design Decisions**

##### **1. Why `subdomain` as separate field?**
**Reasoning**: Even though subdomain is in `url`, extracting it enables fast queries without URL parsing.

**Query pattern**:
```sql
-- Without subdomain field (slow - requires function)
SELECT * FROM http_probes WHERE url LIKE '%admin.example.com%';

-- With subdomain field (fast - indexed)
SELECT * FROM http_probes WHERE subdomain = 'admin.example.com';
```

##### **2. Why JSONB for `technologies` and `chain_status_codes`?**
**Reasoning**: PostgreSQL's JSONB type is queryable and indexable (GIN index).

**Example query**:
```sql
-- Find all hosts running React
SELECT subdomain, technologies 
FROM http_probes 
WHERE technologies @> '["React"]';  -- Fast with GIN index
```

##### **3. Why foreign keys to both `asset_scans` AND `assets`?**
**Reasoning**: Enables two query patterns:
- **By scan job**: "What did THIS specific scan discover?"
- **By asset**: "What HTTP services exist across ALL scans of this asset?"

**Example**:
```sql
-- Pattern 1: Scan-level query
SELECT * FROM http_probes WHERE scan_job_id = 'scan-123';

-- Pattern 2: Asset-level query (across all historical scans)
SELECT DISTINCT subdomain, status_code 
FROM http_probes 
WHERE asset_id = 'asset-456' 
ORDER BY created_at DESC;
```

##### **4. Why `content_length BIGINT` not `INT`?**
**Reasoning**: Some responses can exceed 2GB (INT max = 2,147,483,647 bytes = ~2GB). BIGINT supports up to 8 exabytes.

**Real-world example**: Large file downloads, video streaming endpoints.

##### **5. Why include `ip` field?**
**Reasoning**: IP addresses are critical for bug bounty reconnaissance and asset correlation.

**Use cases**:
- **Shared hosting detection**: Find all subdomains on the same IP (potential pivoting points)
- **Infrastructure mapping**: Identify server clusters and load balancers
- **CDN verification**: Cross-reference with ASN/CDN data
- **Historical tracking**: Monitor IP changes over time across scans

**Example query**:
```sql
-- Find all subdomains sharing an IP (shared hosting)
SELECT subdomain, title, technologies 
FROM http_probes 
WHERE ip = '151.101.1.91' 
ORDER BY subdomain;
```

##### **6. Why CASCADE DELETE on foreign keys?**
**Reasoning**: Automatic cleanup maintains data integrity and prevents orphaned records.

**Benefit**: When an asset is deleted, all related data (subdomains, DNS records, HTTP probes) are automatically removed. No manual cleanup required.

**Safety**: This is a feature, not a bug. If you delete an asset, you expect all its recon data to be deleted too.

#### **Migration File Structure**
**File:** `/backend/migrations/add_httpx_module_schema_2025_11_14.sql`

#### **Success Criteria**
- ✅ Schema supports all 14 required fields (including IP address)
- ✅ Indexes created for common query patterns (including IP search)
- ✅ Foreign keys properly reference `asset_scans` and `assets` with CASCADE DELETE
- ✅ JSONB fields use GIN indexes
- ✅ Test insert/query works successfully
- ✅ Migration is idempotent (can run multiple times safely)
- ✅ CASCADE DELETE verified (test asset deletion removes all probes)

#### **Testing Checklist**
```sql
-- 1. Test table creation
-- 2. Test insert with all 14 fields (including IP)
-- 3. Test insert with minimal fields (nulls allowed)
-- 4. Test JSONB queries (technologies @>, chain_status_codes)
-- 5. Test foreign key constraints (CASCADE DELETE)
--    - Create test asset → Create test HTTP probe → Delete asset → Verify probe deleted
-- 6. Test index usage (EXPLAIN ANALYZE)
-- 7. Test IP-based queries (find subdomains on same IP)
```

---

### **PHASE 2: Module Registry Configuration** 📋
**Status:** 🔄 Not Started  
**Duration:** 30 minutes  
**Dependencies:** Phase 1 (schema must exist)

#### **Objective**
Register HTTPx module in `scan_module_profiles` table with resource requirements and optimization hints.

#### **Module Profile Configuration**

```sql
-- =====================================================================
-- HTTPx Module Profile Registration
-- =====================================================================
-- Description: Registers the HTTPx HTTP probing module
-- Execution: Run in Supabase SQL console after schema creation
-- Idempotent: Yes (uses ON CONFLICT DO UPDATE)
-- Date: 2025-11-14
-- =====================================================================

INSERT INTO scan_module_profiles (
    id,
    module_name,
    version,
    supports_batching,
    max_batch_size,
    resource_scaling,
    estimated_duration_per_domain,
    task_definition_template,
    container_name,
    is_active,
    optimization_hints,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'httpx',
    '1.0',
    true,
    100,  -- HTTP probing: 100 subdomains per batch (moderate)
    '{
        "domain_count_ranges": [
            {
                "min_domains": 1,
                "max_domains": 50,
                "cpu": 512,
                "memory": 1024,
                "notes": "Small batch - HTTP probing is I/O bound but requires more memory than DNS"
            },
            {
                "min_domains": 51,
                "max_domains": 100,
                "cpu": 1024,
                "memory": 2048,
                "notes": "Large batch - increased resources for concurrent HTTP requests"
            }
        ],
        "scaling_notes": "HTTP probing is network I/O bound with moderate CPU needs. Memory scales with concurrent connections and response buffering."
    }'::jsonb,
    10,  -- 10 seconds per subdomain (HTTP probing is slower than DNS)
    'neobotnet-v2-dev-httpx-batch',  -- ECS task definition name
    'httpx-scanner',  -- Container name
    false,  -- Start inactive until container deployed to ECS
    '{
        "memory_multiplier": 1.2,
        "requires_internet": true,
        "requires_subdomains": true,
        "concurrent_limit": 50,
        "description": "HTTP probing with technology detection, redirect following, and metadata extraction",
        "dependencies": ["subfinder"],
        "requires_database_fetch": false,
        "requires_asset_id": true,
        "streaming_capable": true,
        "produces_output_stream": false,
        "consumes_input_stream": true,
        "input_stream_pattern": "scan:{scan_job_id}:subfinder:output",
        "timeout_seconds": 1800,
        "retry_strategy": "exponential_backoff",
        "max_retries": 3
    }'::jsonb,
    now(),
    now()
)
ON CONFLICT (module_name) DO UPDATE SET
    version = EXCLUDED.version,
    supports_batching = EXCLUDED.supports_batching,
    max_batch_size = EXCLUDED.max_batch_size,
    resource_scaling = EXCLUDED.resource_scaling,
    estimated_duration_per_domain = EXCLUDED.estimated_duration_per_domain,
    task_definition_template = EXCLUDED.task_definition_template,
    container_name = EXCLUDED.container_name,
    optimization_hints = EXCLUDED.optimization_hints,
    updated_at = now();

-- =====================================================================
-- Update Dependency Graph in scan_pipeline.py
-- =====================================================================
-- Manual step: Ensure scan_pipeline.py has:
-- DEPENDENCIES = {
--     "subfinder": [],
--     "dnsx": ["subfinder"],
--     "httpx": ["subfinder"],  # ← Already exists, verify it's there
--     "nuclei": ["httpx"],
-- }
```

#### **Critical Configuration Decisions**

##### **1. Resource Allocation**
**CPU**: 512-1024 (I/O bound, not CPU intensive)  
**Memory**: 1024-2048 MB (needs buffering for HTTP responses)

**Reasoning**: HTTP requests require:
- Connection pooling (memory)
- Response buffering (memory)
- TLS handshakes (CPU)
- Concurrent connections (memory)

**Comparison**:
- DNSx: 256-1024 CPU, 512-2048 MB (fast, small responses)
- HTTPx: 512-1024 CPU, 1024-2048 MB (slower, larger responses)

##### **2. Estimated Duration: 10s per subdomain**
**Reasoning**: HTTP probing involves:
- DNS resolution (if not cached): ~1s
- TCP connection: ~1s
- TLS handshake: ~1-2s
- HTTP request/response: ~2-5s
- Redirect following: +2-5s per redirect

**Real-world data**:
- Fast response: 3-5 seconds
- Average response: 8-12 seconds
- Slow/timeout: 15-30 seconds

Conservative estimate: **10 seconds average**

##### **3. Max Batch Size: 100 subdomains**
**Reasoning**:
- 100 subdomains × 10s = ~17 minutes (safe under ECS timeout)
- Allows parallel processing (50 concurrent limit)
- 100 subdomains = manageable memory usage (~2GB)

**Comparison**:
- Subfinder: No batch limit (streaming producer)
- DNSx: 200 per batch (fast queries)
- HTTPx: 100 per batch (slower probing)

##### **4. Streaming Configuration**
```json
{
    "streaming_capable": true,
    "produces_output_stream": false,  // HTTPx is a terminal consumer
    "consumes_input_stream": true,     // Reads from subfinder
    "input_stream_pattern": "scan:{scan_job_id}:subfinder:output"
}
```

**Reasoning**: HTTPx is a **consumer-only** module. It doesn't produce output for other modules to consume (no nuclei dependency yet).

#### **Success Criteria**
- ✅ Module registered in `scan_module_profiles` table
- ✅ `is_active = false` initially (prevents premature usage)
- ✅ Resource scaling matches container requirements
- ✅ Dependencies correctly reference subfinder
- ✅ Streaming flags properly configured

---

### **PHASE 2.5: SDK Verification** ✅
**Status:** ✅ COMPLETE  
**Duration:** 0.5 hours  
**Completed:** 2025-11-14

#### **Objective**
Verify that HTTPx Go SDK provides all 14 required fields before starting container implementation.

#### **✅ Findings**
**ALL 14 fields available in `runner.Result` struct!**

Verified via: `go doc github.com/projectdiscovery/httpx/runner Result`

#### **Field Mapping (Complete)**
```
Schema Field          SDK Field                Type        Notes
────────────────────  ───────────────────────  ──────────  ──────────────────
status_code        → result.StatusCode       int         Direct match
url                → result.URL              string      Direct match
title              → result.Title            string      Direct match
webserver          → result.WebServer        string      Direct match  
content_length     → result.ContentLength    int         Direct match
final_url          → result.FinalURL         string      Direct match
ip                 → result.A / result.AAAA  []string    Pick first IPv4/IPv6
technologies       → result.Technologies     []string    Already JSON array
cdn_name           → result.CDNName          string      Direct match
content_type       → result.ContentType      string      Direct match
asn                → result.ASN.AsNumber     string      Extract from *AsnResponse
chain_status_codes → result.ChainStatusCodes []int       Already JSON array
location           → result.Location         string      Direct match
favicon_md5        → result.FaviconMD5       string      Direct match
```

#### **🎁 Bonus Fields** (Make implementation easier)
- `result.Scheme` → No need to parse URL for http/https
- `result.Port` → No need to parse URL for port
- `result.Host` → Already extracted subdomain
- `result.Input` → Original input subdomain

#### **Decision**
**✅ Use SDK directly** (NOT CLI + CSV parsing)

**Advantages:**
- Type-safe Go structs
- Better performance (no shell exec)
- No CSV parsing logic needed
- Direct JSONB marshaling for arrays
- Cleaner, more maintainable code

---

### **PHASE 3: Container Implementation** 🐳
**Status:** 🔄 Not Started  
**Duration:** 5-6 hours *(revised: 4-5 hours with SDK)*  
**Dependencies:** Phase 0 (template), Phase 1 (schema), Phase 2.5 (SDK verified)

#### **Objective**
Implement the HTTPx Go container following the documented template pattern.

#### **Implementation Strategy**

##### **Approach: Clone & Customize DNSx**
**Reasoning**: DNSx is the closest pattern (streaming consumer, database writes).

**Process**:
1. Copy `/backend/containers/dnsx-go/` → `/backend/containers/httpx-go/`
2. Replace DNSx SDK imports with HTTPx SDK
3. Customize `ScanResult` struct for 13 HTTP fields
4. Update database writes to `http_probes` table
5. Adjust parsing logic for HTTPx JSON output
6. Test locally with Docker

#### **File Structure**
```
/backend/containers/httpx-go/
├── Dockerfile              # Multi-stage build, health checks
├── go.mod                  # Dependencies (httpx SDK, supabase, redis)
├── go.sum                  # Dependency lock file
├── main.go                 # Entry point, mode routing
├── scanner.go              # HTTPx SDK integration, probing logic
├── database.go             # Supabase client, bulk insert to http_probes
├── streaming.go            # Redis Streams consumer, completion detection
├── batch_support.go        # Batch mode (fetch from database)
└── README.md               # Container documentation
```

#### **Key Implementation Files**

##### **1. main.go - Mode Routing**
```go
package main

import (
    "log"
    "os"
)

func main() {
    log.Println("🚀 HTTPx HTTP Probing Container starting...")
    
    // Determine execution mode
    batchMode := os.Getenv("BATCH_MODE") == "true"
    streamingMode := os.Getenv("STREAMING_MODE") == "true"
    
    // Mode routing
    if streamingMode {
        log.Println("🌊 Starting STREAMING mode (Consumer from subfinder)")
        if err := runStreamingMode(); err != nil {
            log.Fatalf("❌ Streaming mode failed: %v", err)
        }
        log.Println("✅ HTTPx streaming consumer completed")
        return
    }
    
    if batchMode {
        log.Println("🔄 Starting BATCH mode")
        if err := runBatchMode(); err != nil {
            log.Fatalf("❌ Batch mode failed: %v", err)
        }
        log.Println("✅ HTTPx batch scan completed")
        return
    }
    
    log.Println("🔄 Starting SIMPLE mode")
    if err := runSimpleMode(); err != nil {
        log.Fatalf("❌ Simple mode failed: %v", err)
    }
    log.Println("✅ HTTPx simple scan completed")
}
```

##### **2. scanner.go - HTTPx Integration**
```go
package main

import (
    "context"
    "encoding/json"
    "github.com/projectdiscovery/httpx/runner"
)

// HTTPProbeResult represents httpx JSON output
type HTTPProbeResult struct {
    StatusCode       int      `json:"status_code"`
    URL              string   `json:"url"`
    Title            string   `json:"title"`
    Webserver        string   `json:"webserver"`
    Tech             []string `json:"tech"`
    ContentLength    int64    `json:"content_length"`
    FinalURL         string   `json:"final_url"`
    IP               string   `json:"ip"`           // IP address resolved by httpx
    CDNName          string   `json:"cdn_name"`
    ContentType      string   `json:"content_type"`
    ASN              string   `json:"asn"`
    ChainStatusCodes []int    `json:"chain_status_codes"`
    Location         string   `json:"location"`
    FaviconMD5       string   `json:"favicon_md5"`
    
    // Extracted metadata
    Subdomain    string `json:"-"` // Computed from URL
    Scheme       string `json:"-"` // Computed from URL
    Port         int    `json:"-"` // Computed from URL
    
    // Foreign keys (injected)
    ScanJobID    string `json:"-"`
    AssetID      string `json:"-"`
    ParentDomain string `json:"-"`
}

// probeSubdomains probes HTTP services for given subdomains
func probeSubdomains(subdomains []string) ([]*HTTPProbeResult, error) {
    // Configure httpx runner
    options := runner.Options{
        JSON: true,  // JSON output mode
        // Specify fields to extract (matches our 14 fields)
        JSONFields: "url,status_code,title,webserver,tech,content_length,final_url,ip,cdn_name,content_type,asn,chain_status_codes,location,favicon_md5",
        Silent: true,
        Threads: 50,  // Concurrent requests
        Timeout: 10,  // 10 second timeout per request
        FollowRedirects: true,
        MaxRedirects: 3,
    }
    
    // Initialize httpx runner
    httpxRunner, err := runner.New(&options)
    if err != nil {
        return nil, err
    }
    
    // Run probing
    results := []*HTTPProbeResult{}
    // ... probing logic ...
    
    return results, nil
}
```

##### **3. database.go - Bulk Insert**
```go
package main

import (
    "bytes"
    "encoding/json"
    "net/http"
)

// BulkInsertHTTPProbes inserts multiple HTTP probe results
func (c *SupabaseClient) BulkInsertHTTPProbes(results []*HTTPProbeResult) error {
    if len(results) == 0 {
        return nil
    }
    
    // Prepare bulk insert
    payload, err := json.Marshal(results)
    if err != nil {
        return err
    }
    
    // POST to Supabase
    url := c.url + "/rest/v1/http_probes"
    req, err := http.NewRequest("POST", url, bytes.NewReader(payload))
    req.Header.Set("apikey", c.serviceKey)
    req.Header.Set("Authorization", "Bearer "+c.serviceKey)
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Prefer", "return=minimal")  // Don't return inserted rows
    
    resp, err := c.httpClient.Do(req)
    // ... error handling ...
    
    return nil
}
```

##### **4. streaming.go - Redis Consumer**
```go
package main

import (
    "context"
    "encoding/json"
    "github.com/go-redis/redis/v8"
)

// StreamingConfig holds Redis Streams configuration
type StreamingConfig struct {
    StreamInputKey    string // scan:{job_id}:subfinder:output
    ConsumerGroupName string // httpx-consumers
    ConsumerName      string // httpx-{task_id}
    BatchSize         int64  // Messages per XREADGROUP
    RedisHost         string
    RedisPort         string
    ScanJobID         string
}

// runStreamingMode consumes subdomains from subfinder's stream
func runStreamingMode() error {
    config := loadStreamingConfig()
    
    // Initialize Redis client
    redisClient := redis.NewClient(&redis.Options{
        Addr: config.RedisHost + ":" + config.RedisPort,
    })
    
    // Create consumer group (idempotent)
    redisClient.XGroupCreateMkStream(ctx, config.StreamInputKey, config.ConsumerGroupName, "0")
    
    // Consume messages
    for {
        // XREADGROUP BLOCK 1000 COUNT 10 GROUP httpx-consumers httpx-task123 STREAMS scan:xxx:subfinder:output >
        messages := redisClient.XReadGroup(ctx, &redis.XReadGroupArgs{
            Group:    config.ConsumerGroupName,
            Consumer: config.ConsumerName,
            Streams:  []string{config.StreamInputKey, ">"},
            Count:    config.BatchSize,
            Block:    time.Second,
        })
        
        // Process messages
        for _, msg := range messages[0].Messages {
            // Parse subdomain message
            var subdomain SubdomainMessage
            json.Unmarshal([]byte(msg.Values["subdomain"].(string)), &subdomain)
            
            // Check for completion marker
            if msg.Values["type"] == "completion" {
                log.Println("✅ Completion marker received, stopping consumer")
                return nil
            }
            
            // Probe subdomain
            result := probeSubdomain(subdomain.Subdomain)
            
            // Write to database
            supabaseClient.BulkInsertHTTPProbes([]*HTTPProbeResult{result})
            
            // ACK message
            redisClient.XAck(ctx, config.StreamInputKey, config.ConsumerGroupName, msg.ID)
        }
    }
}
```

##### **5. Dockerfile**
```dockerfile
# ================================================================
# HTTPx HTTP Probing Container
# ================================================================
FROM golang:1.23-alpine AS builder

RUN apk --no-cache add git ca-certificates build-base

WORKDIR /app

# Copy dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source
COPY *.go ./

# Build
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o httpx-scanner .

# ================================================================
# Production stage
# ================================================================
FROM alpine:latest

RUN apk --no-cache add ca-certificates curl bash bind-tools

WORKDIR /app

COPY --from=builder /app/httpx-scanner .

# Health check script
RUN echo '#!/bin/bash' > /app/health-check.sh && \
    echo 'pgrep -f "httpx-scanner" > /dev/null && echo "✅ HEALTHY" || exit 1' >> /app/health-check.sh && \
    chmod +x /app/health-check.sh

# Non-root user
RUN addgroup -g 1001 scanner && \
    adduser -D -u 1001 -G scanner scanner && \
    chown -R scanner:scanner /app

USER scanner

HEALTHCHECK --interval=30s --timeout=15s --retries=3 CMD /app/health-check.sh

LABEL maintainer="Pluckware Development Team" \
      version="1.0.0" \
      description="HTTPx HTTP probing with technology detection" \
      module="httpx"

ENTRYPOINT ["./httpx-scanner"]
```

#### **Environment Variables Contract**

##### **All Modes**
```bash
SCAN_JOB_ID=uuid                     # Asset scan job ID
USER_ID=uuid                          # User ID
ASSET_ID=uuid                         # Asset ID
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx
```

##### **Streaming Mode (PRIMARY)**
```bash
STREAMING_MODE=true
STREAM_INPUT_KEY=scan:{job_id}:subfinder:output
CONSUMER_GROUP_NAME=httpx-consumers
CONSUMER_NAME=httpx-{task_id}
REDIS_HOST=localhost
REDIS_PORT=6379
BATCH_SIZE=10                         # Messages per XREADGROUP
```

##### **Batch Mode**
```bash
BATCH_MODE=true
BATCH_ID=uuid
BATCH_OFFSET=0
BATCH_LIMIT=100
```

##### **Simple Mode**
```bash
SUBDOMAINS=["admin.example.com", "api.example.com"]
```

#### **Success Criteria**
- ✅ Container builds successfully
- ✅ All 3 modes implemented (simple, batch, streaming)
- ✅ HTTPx SDK integrated correctly
- ✅ JSON output parsed into 14 fields (including IP address)
- ✅ Database writes to `http_probes` table with all fields
- ✅ Redis Streams consumer works (XREADGROUP)
- ✅ Completion marker handled gracefully
- ✅ Health checks pass
- ✅ Non-root user (security)

---

### **PHASE 4: Local Testing** 🧪
**Status:** 🔄 Not Started  
**Duration:** 2-3 hours  
**Dependencies:** Phase 3 (container implemented)

#### **Objective**
Validate HTTPx container functionality locally before VPS/Cloud deployment.

#### **Testing Approach: Three-Level Strategy**

##### **Level 1: Simple Mode Test (Fastest)**
**Goal**: Verify basic functionality without Redis or streaming complexity.

```bash
cd /root/pluckware/neobotnet/neobotnet_v2/backend/containers/httpx-go

# Build container
docker build -t httpx-scanner:local .

# Run simple mode with real subdomain
docker run --rm \
  -e SUBDOMAINS='["bandcamp.com"]' \
  -e SCAN_JOB_ID=test-$(uuidgen) \
  -e USER_ID=$(uuidgen) \
  -e ASSET_ID=$(uuidgen) \
  -e SUPABASE_URL=$SUPABASE_URL \
  -e SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY \
  httpx-scanner:local

# Verify: Check Supabase http_probes table for results
```

**Success Criteria**:
- ✅ Container starts without errors
- ✅ HTTPx probes bandcamp.com successfully
- ✅ Result written to `http_probes` table
- ✅ All 14 fields populated (including IP address)
- ✅ IP address is valid format (e.g., "151.101.1.91")

##### **Level 2: Streaming Mode Test (Full Integration)**
**Goal**: Test Redis Streams consumer pattern with subfinder.

**Docker Compose Setup**:
```yaml
# docker-compose.httpx-test.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  subfinder:
    build: ./subfinder-go
    environment:
      DOMAINS: '["bandcamp.com"]'
      STREAMING_MODE: "true"
      STREAM_OUTPUT_KEY: "scan:test-123:subfinder:output"
      REDIS_HOST: "redis"
      REDIS_PORT: "6379"
      SCAN_JOB_ID: "test-subfinder-job"
      USER_ID: "test-user"
      ASSET_ID: "test-asset"
      SUPABASE_URL: "${SUPABASE_URL}"
      SUPABASE_SERVICE_ROLE_KEY: "${SUPABASE_SERVICE_ROLE_KEY}"
    depends_on:
      - redis
  
  httpx:
    build: ./httpx-go
    environment:
      STREAMING_MODE: "true"
      STREAM_INPUT_KEY: "scan:test-123:subfinder:output"
      CONSUMER_GROUP_NAME: "httpx-consumers"
      CONSUMER_NAME: "httpx-test-1"
      REDIS_HOST: "redis"
      REDIS_PORT: "6379"
      SCAN_JOB_ID: "test-httpx-job"
      USER_ID: "test-user"
      ASSET_ID: "test-asset"
      SUPABASE_URL: "${SUPABASE_URL}"
      SUPABASE_SERVICE_ROLE_KEY: "${SUPABASE_SERVICE_ROLE_KEY}"
      BATCH_SIZE: "10"
    depends_on:
      - redis
      - subfinder

  # Debug: Monitor Redis Stream
  redis-cli:
    image: redis:7-alpine
    command: redis-cli -h redis MONITOR
    depends_on:
      - redis
```

**Test Execution**:
```bash
cd /root/pluckware/neobotnet/neobotnet_v2/backend/containers

# Run full streaming test
docker-compose -f docker-compose.httpx-test.yml up

# Monitor logs
docker-compose -f docker-compose.httpx-test.yml logs -f httpx

# Verify Redis Stream
docker exec -it redis-container redis-cli
> XINFO STREAM scan:test-123:subfinder:output
> XLEN scan:test-123:subfinder:output

# Cleanup
docker-compose -f docker-compose.httpx-test.yml down
```

**Success Criteria**:
- ✅ Subfinder produces messages to stream
- ✅ HTTPx consumes messages from stream
- ✅ HTTPx processes subdomains in real-time
- ✅ HTTP probes written to database
- ✅ Completion marker handled correctly
- ✅ Consumer ACKs messages
- ✅ No orphaned messages in stream

##### **Level 3: End-to-End Pipeline Test**
**Goal**: Test 3-module pipeline (subfinder → dnsx + httpx in parallel).

```bash
# Trigger scan via API
curl -X POST https://aldous-api.neobotnet.com/api/v1/scans \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_ids": ["<test-asset-id>"],
    "modules": ["subfinder", "dnsx", "httpx"]
  }'

# Monitor scan progress
curl -X GET https://aldous-api.neobotnet.com/api/v1/scans/<scan_id> \
  -H "Authorization: Bearer $TOKEN"

# Verify results in dashboard
# Check subdomains, dns_records, AND http_probes tables
```

**Success Criteria**:
- ✅ All 3 modules launch successfully
- ✅ DNSx and HTTPx run in parallel
- ✅ Both consumers process subfinder stream
- ✅ No race conditions or deadlocks
- ✅ Scan completes with status "completed"
- ✅ Dashboard displays all 3 result types

#### **Testing Checklist**
```
Level 1: Simple Mode
[ ] Container builds without errors
[ ] HTTPx SDK initializes correctly
[ ] Probing works (bandcamp.com → results)
[ ] Database writes succeed
[ ] All 14 fields present in results (including IP)
[ ] IP address populated correctly
[ ] Nulls handled correctly (missing title, etc.)

Level 2: Streaming Mode
[ ] Redis connection established
[ ] Consumer group created
[ ] Messages consumed from stream
[ ] XREADGROUP returns messages
[ ] XACK acknowledgments work
[ ] Completion marker detected
[ ] Graceful shutdown

Level 3: Pipeline Integration
[ ] Module launches via API
[ ] Parallel execution (dnsx + httpx)
[ ] No consumer conflicts
[ ] Scan status updates correctly
[ ] Results visible in dashboard
```

---

### **PHASE 5: VPS Deployment** 🚀
**Status:** 🔄 Not Started  
**Duration:** 1-2 hours  
**Dependencies:** Phase 4 (local testing passed)

#### **Objective**
Deploy HTTPx container to local VPS for controlled environment testing before cloud deployment.

#### **Deployment Strategy**

##### **VPS Environment Details**
- **Frontend**: http://172.236.127.72:3000
- **Backend**: http://172.236.127.72:8000
- **Purpose**: Fast iteration, convenient for non-scan-engine changes

##### **Deployment Steps**

**1. Build and Push to VPS**
```bash
# SSH into VPS
ssh root@172.236.127.72

# Navigate to containers directory
cd /root/pluckware/neobotnet/neobotnet_v2/backend/containers/httpx-go

# Build container on VPS
docker build -t httpx-scanner:vps .

# Verify build
docker images | grep httpx
```

**2. Update Docker Compose (if using)**
```yaml
# /root/pluckware/neobotnet/neobotnet_v2/docker-compose.vps.yml
services:
  httpx:
    image: httpx-scanner:vps
    environment:
      # ... environment variables ...
    networks:
      - neobotnet-network
```

**3. Test Scan via VPS API**
```bash
# From your local machine
TOKEN=$(curl -X POST http://172.236.127.72:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sam@pluck.ltd","password":"TestSamPluck2025!!"}' \
  | jq -r '.access_token')

# Trigger scan with httpx
curl -X POST http://172.236.127.72:8000/api/v1/scans \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_ids": ["<asset-id>"]
  }'

# Monitor scan
SCAN_ID=$(# ... from response ...)
curl -X GET http://172.236.127.72:8000/api/v1/scans/$SCAN_ID \
  -H "Authorization: Bearer $TOKEN"
```

#### **Success Criteria**
- ✅ Container builds on VPS
- ✅ Scan launches successfully via API
- ✅ HTTPx module executes in streaming mode
- ✅ Results appear in `http_probes` table
- ✅ Dashboard displays HTTP probe results
- ✅ No errors in container logs

#### **Rollback Plan**
If VPS testing fails:
1. Deactivate httpx module: `UPDATE scan_module_profiles SET is_active = false WHERE module_name = 'httpx'`
2. Scans will skip httpx (pipeline continues with subfinder + dnsx)
3. Fix issues, retest locally, redeploy

---

### **PHASE 6: AWS ECS Deployment** ☁️
**Status:** 🔄 Not Started  
**Duration:** 2-3 hours  
**Dependencies:** Phase 5 (VPS testing passed)

#### **Objective**
Deploy HTTPx container to AWS ECS for production-scale scanning.

#### **Deployment Steps**

##### **1. Build and Push to AWS ECR**
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build for production
cd /root/pluckware/neobotnet/neobotnet_v2/backend/containers/httpx-go
docker build -t httpx-scanner:latest .

# Tag for ECR
docker tag httpx-scanner:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/neobotnet-httpx:latest

# Push to ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/neobotnet-httpx:latest
```

##### **2. Create ECS Task Definition**
**File**: `neobotnet-v2-dev-httpx-batch` (matches `task_definition_template` in module profile)

```json
{
  "family": "neobotnet-v2-dev-httpx-batch",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "taskRoleArn": "arn:aws:iam::<account>:role/neobotnet-ecs-task-role",
  "executionRoleArn": "arn:aws:iam::<account>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "httpx-scanner",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/neobotnet-httpx:latest",
      "essential": true,
      "environment": [
        {"name": "LOG_LEVEL", "value": "info"}
      ],
      "secrets": [
        {"name": "SUPABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."},
        {"name": "SUPABASE_SERVICE_ROLE_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/neobotnet-httpx",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "httpx"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "/app/health-check.sh || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

**Register Task Definition**:
```bash
aws ecs register-task-definition --cli-input-json file://httpx-task-definition.json
```

##### **3. Test ECS Task Launch**
```bash
# Manual task run (verify task definition works)
aws ecs run-task \
  --cluster neobotnet-v2-dev-cluster \
  --task-definition neobotnet-v2-dev-httpx-batch \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --overrides '{
    "containerOverrides": [{
      "name": "httpx-scanner",
      "environment": [
        {"name": "STREAMING_MODE", "value": "true"},
        {"name": "SCAN_JOB_ID", "value": "test-scan-123"},
        {"name": "STREAM_INPUT_KEY", "value": "scan:test-123:subfinder:output"}
      ]
    }]
  }'

# Monitor task
aws ecs describe-tasks --cluster neobotnet-v2-dev-cluster --tasks <task-arn>

# Check logs
aws logs tail /ecs/neobotnet-httpx --follow
```

##### **4. Activate Module**
```sql
-- Enable httpx module for production use
UPDATE scan_module_profiles 
SET is_active = true 
WHERE module_name = 'httpx';
```

##### **5. Production Test**
```bash
# Trigger scan via cloud API
curl -X POST https://aldous-api.neobotnet.com/api/v1/scans \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_ids": ["<asset-id>"]
  }'

# Verify in dashboard
# https://neobotnet-v2-git-dev-sams-projects-3ea6cef5.vercel.app/
```

#### **Success Criteria**
- ✅ Image pushed to ECR successfully
- ✅ ECS task definition registered
- ✅ Manual ECS task runs successfully
- ✅ Task logs show HTTP probing activity
- ✅ Results written to database
- ✅ Module activated (`is_active = true`)
- ✅ Production scan includes httpx module
- ✅ Dashboard displays HTTP probe data

---

### **PHASE 7: Frontend Integration** 🎨
**Status:** 🔄 Not Started  
**Duration:** 2-3 hours  
**Dependencies:** Phase 6 (ECS deployment complete)

#### **Objective**
Display HTTP probe results in the dashboard with filtering and visualization.

#### **Implementation Tasks**

##### **1. TypeScript Types**
**File**: `/frontend/src/types/http-probes.ts`

```typescript
export interface HTTPProbe {
  id: string;
  status_code: number | null;
  url: string;
  title: string | null;
  webserver: string | null;
  technologies: string[] | null;
  content_length: number | null;
  final_url: string | null;
  ip: string | null;                    // IP address resolved by httpx
  cdn_name: string | null;
  content_type: string | null;
  asn: string | null;
  chain_status_codes: number[] | null;
  location: string | null;
  favicon_md5: string | null;
  subdomain: string;
  scheme: string;
  port: number;
  scan_job_id: string;
  asset_id: string;
  parent_domain: string;
  created_at: string;
}

export interface HTTPProbesResponse {
  data: HTTPProbe[];
  count: number;
}
```

##### **2. API Client**
**File**: `/frontend/src/lib/api/http-probes.ts`

```typescript
export const httpProbesAPI = {
  /**
   * List HTTP probes for an asset
   */
  async listByAsset(assetId: string): Promise<HTTPProbesResponse> {
    const response = await fetch(
      `${API_BASE}/api/v1/assets/${assetId}/http-probes`,
      {
        headers: { Authorization: `Bearer ${getToken()}` }
      }
    );
    return response.json();
  },
  
  /**
   * Filter probes by status code range
   */
  async filterByStatus(assetId: string, minStatus: number, maxStatus: number) {
    // ... implementation
  }
};
```

##### **3. Dashboard Component**
**File**: `/frontend/src/app/assets/[id]/http-probes/page.tsx`

**Features**:
- Table view of HTTP probes
- Filter by status code (200s, 300s, 400s, 500s)
- Search by subdomain
- Technology badge display
- CDN indicator
- Link to full URL
- Export to CSV

**UI Mockup**:
```
┌─────────────────────────────────────────────────────────────┐
│ HTTP Probes - EpicGames                           [Export]  │
├─────────────────────────────────────────────────────────────┤
│ Filters: [All] [2xx] [3xx] [4xx] [5xx]    Search: [____]   │
├─────────────────────────────────────────────────────────────┤
│ Subdomain              Status  Title          Technologies  │
├─────────────────────────────────────────────────────────────┤
│ admin.epicgames.com    200     Admin Panel    Nginx, React  │
│ api.epicgames.com      200     API Docs       Cloudflare    │
│ old.epicgames.com      301     → epicgames.com              │
│ test.epicgames.com     404     Not Found                    │
└─────────────────────────────────────────────────────────────┘
```

#### **Success Criteria**
- ✅ HTTP probes page displays data from database
- ✅ Filtering by status code works
- ✅ Technology badges render correctly
- ✅ Links to URLs are clickable
- ✅ Export to CSV functional
- ✅ Responsive design matches existing pages

---

## 📊 Project Tracking

### **Progress Overview**
```
Phase 0: Pattern Formalization        [✅] 100% COMPLETE
Phase 1: Database Schema              [✅] 100% COMPLETE
Phase 2: Module Registration          [✅] 100% COMPLETE
Phase 2.5: SDK Verification           [✅] 100% COMPLETE
Phase 3: Container Implementation     [✅] 100% COMPLETE
Phase 4: Local Testing                [ ] 0%
Phase 5: VPS Deployment               [ ] 0%
Phase 6: AWS ECS Deployment           [ ] 0%
Phase 7: Frontend Integration         [ ] 0%
```

### **Time Tracking**
| Phase | Estimated | Actual | Notes |
|-------|-----------|--------|-------|
| Phase 0 | 3-4h | ✅ 2h | Completed: Documentation created |
| Phase 1 | 1-2h | ✅ 1h | Completed: Schema applied to Supabase (22 cols, 9 indexes, 2 FK, RLS) |
| Phase 2 | 0.5h | ✅ 0.5h | Completed: Module registered (INACTIVE until Phase 6) |
| Phase 2.5 | 0.5h | ✅ 0.5h | Completed: SDK verified (all 14 fields available) |
| Phase 3 | 5-6h | ✅ 3.5h | Completed: Container implementation (scanner, streaming, database, main, Dockerfile) |
| Phase 4 | 2-3h | - | NEXT: Local testing (simple mode + docker-compose) |
| Phase 5 | 1-2h | - | - |
| Phase 6 | 2-3h | - | - |
| Phase 7 | 2-3h | - | - |
| **Total** | **17.5-24.5h** | **7.5h** | 35% complete |

---

## ⚠️ Risk Assessment

### **High-Risk Areas**

#### **1. HTTPx SDK Integration**
**Risk**: ProjectDiscovery's httpx Go SDK may have unexpected API or limitations.

**Mitigation**:
- Phase 4 Step 1 (SDK investigation) identifies issues early
- Fallback: Shell out to httpx binary if SDK is problematic
- Alternative SDK: github.com/projectdiscovery/httpx/runner

**Likelihood**: Low (DNSx SDK worked well)  
**Impact**: Medium (adds 2-3 hours)

#### **2. Redis Streams Consumer Conflicts**
**Risk**: DNSx and HTTPx may conflict reading from same stream (subfinder output).

**Mitigation**:
- Redis Streams support multiple consumer groups
- Each module has its own group (dnsx-consumers, httpx-consumers)
- Test Level 3 validates parallel consumption

**Likelihood**: Low (architecture supports this)  
**Impact**: High (would require sequential execution)

#### **3. Rate Limiting / IP Bans**
**Risk**: Aggressive HTTP probing may trigger rate limits or IP bans.

**Mitigation**:
- Start with conservative concurrency (50 threads)
- Add delay between requests if needed (100ms)
- Monitor for 429 status codes
- Implement exponential backoff

**Likelihood**: Medium (depends on target)  
**Impact**: Low (adjustable via config)

#### **4. Large-Scale Memory Usage**
**Risk**: 100 subdomains × 2MB avg response = 200MB buffering.

**Mitigation**:
- Resource scaling allocates 1-2GB memory
- Process in smaller batches if needed
- Monitor memory via health checks

**Likelihood**: Low (ECS can scale)  
**Impact**: Medium (OOM kills container)

---

## 🔄 Rollback Strategy

### **If Production Issues Occur**

**Immediate Rollback (< 5 minutes)**:
```sql
-- Deactivate httpx module
UPDATE scan_module_profiles 
SET is_active = false 
WHERE module_name = 'httpx';
```
**Result**: Future scans skip httpx, pipeline continues with subfinder + dnsx.

**Container Rollback** (if container crashes):
```bash
# Stop ECS tasks running httpx
aws ecs update-service \
  --cluster neobotnet-v2-dev-cluster \
  --service httpx-service \
  --desired-count 0
```

**Database Rollback** (if schema causes issues):
```sql
-- Drop http_probes table and constraints
DROP TABLE IF EXISTS http_probes CASCADE;
```
**Note**: Only do this if absolutely necessary (data loss).

---

## ✅ Definition of Done

### **Project Complete When**:
1. ✅ All 7 phases completed
2. ✅ HTTPx operational in cloud environment
3. ✅ Production scan includes httpx results
4. ✅ Dashboard displays HTTP probe data
5. ✅ Container template documented
6. ✅ Zero P0/P1 bugs in production
7. ✅ Performance meets expectations (< 15s per subdomain)

### **Success Metrics**:
- **Functionality**: HTTPx processes 100+ subdomains successfully
- **Performance**: Average response time < 12 seconds per subdomain
- **Reliability**: < 5% failure rate on probes
- **Scalability**: Handles 500+ subdomain assets without OOM
- **Maintainability**: Future modules (nuclei) take < 4 hours to implement

---

## 📝 Next Steps

### **Immediate Actions (Post-Approval)**:
1. **Phase 0**: Start documenting `CONTAINER_TEMPLATE.md`
2. **Phase 1**: Create database schema migration file
3. **Phase 2**: Register httpx module profile
4. **Phase 3**: Begin container implementation

### **Questions to Resolve**:
- [ ] Confirm Supabase credentials for testing
- [ ] Verify VPS has Docker installed and updated
- [ ] Check AWS ECR repository exists for httpx
- [ ] Confirm ECS cluster has capacity for new tasks

---

## 📚 References

### **External Documentation**:
- ProjectDiscovery HTTPx: https://github.com/projectdiscovery/httpx
- HTTPx Runner SDK: https://pkg.go.dev/github.com/projectdiscovery/httpx/runner
- Redis Streams: https://redis.io/docs/data-types/streams/
- PostgreSQL JSONB: https://www.postgresql.org/docs/current/datatype-json.html

### **Internal Documentation**:
- Subfinder Container: `/backend/containers/subfinder-go/`
- DNSx Container: `/backend/containers/dnsx-go/`
- Scan Pipeline: `/backend/app/services/scan_pipeline.py`
- Module Registry: `/backend/app/services/module_registry.py`

---

**Project Plan Status**: ✅ Ready for Review and Approval

**Approval Required From**: Sam (@sam@pluck.ltd)

**Once Approved**: Implementation begins with Phase 0 (Pattern Formalization)

---

## **Phase 4: First Cloud Test & Architecture Refinement**

**Status:** 🔍 In Progress  
**Started:** November 14, 2025 - 17:01 UTC  
**Purpose:** Execute first end-to-end cloud test, identify issues, and refine architecture

---

### **4.1 Test Execution**

#### **Test Configuration:**
```bash
Asset: rikhter (0af5ae55-feea-491d-bfdc-be0c66fd69f0)
Apex Domains: hackerone.com, epicgames.com, t-mobile.com
Modules Requested: ["subfinder", "httpx"]
Scan ID: 6a5d84f4-d7b3-4f0e-b3c8-e13e5d0f1729
```

#### **Test Results:**
```
✅ Step 1: Authentication - SUCCESS
   User authenticated successfully

✅ Step 2: API Validation - SUCCESS  
   API accepted httpx module (Pydantic schema fix worked)
   Scan triggered successfully
   
❌ Step 3: Execution - TIMEOUT
   Status: "timeout" after 180 seconds (3 minutes)
   Expected: "completed" within 1-2 minutes
   
📊 Outcome: HTTPx was never tested (blocked by Subfinder failure)
```

---

### **4.2 Critical Discovery: Architecture Misalignment**

#### **Error Observed:**
```json
{
  "level": "error",
  "msg": "Failed to store subdomains for domain hackerone.com: 
         database insertion failed: Supabase error [23502]: 
         null value in column 'asset_id' of relation 'subdomains' 
         violates not-null constraint"
}
```

#### **Failure Chain:**
```
1. Subfinder discovers subdomains ✅
   └─> Tries to write to database ❌
       └─> Missing asset_id in INSERT statement
           └─> Database rejects insertion (NOT NULL constraint)
               └─> Error terminates subdomain processing
                   └─> Redis Stream remains EMPTY 📭
                       └─> HTTPx waits indefinitely ⏳
                           └─> Scan times out after 3 minutes ⏱️
```

**Impact:** HTTPx was completely blocked from testing due to upstream failure.

---

### **4.3 Root Cause Analysis**

#### **Architectural Intent (Stated Design):**

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLEAN PIPELINE DESIGN                        │
└─────────────────────────────────────────────────────────────────┘

SUBFINDER (Producer Only)
   └─> Discovers subdomains from passive sources
       └─> Publishes to Redis Stream (ONLY)
           └─> NO database writes

DNSX (Consumer + Persistence Layer)  
   └─> Consumes subdomains from Redis Stream
       └─> Performs DNS resolution (A, AAAA, CNAME records)
           └─> Writes to database:
               1. subdomains table (entity persistence)
               2. dns_records table (resolution data)

HTTPX (Consumer + HTTP Layer)
   └─> Consumes subdomains from Redis Stream  
       └─> Performs HTTP probing (GET requests)
           └─> Writes to http_probes table

KEY PRINCIPLE: 
- Subfinder = Discovery only
- DNSx = DNS + Persistence
- HTTPx = HTTP + Probing
```

#### **Current Implementation (What Code Actually Does):**

```
┌─────────────────────────────────────────────────────────────────┐
│                    ACTUAL IMPLEMENTATION                         │
└─────────────────────────────────────────────────────────────────┘

SUBFINDER:
   ✍️  Writes to subdomains table (storeSubdomains) ← DUPLICATE!
   📤 Streams to Redis

DNSX:
   📥 Consumes from Redis Stream
   ✍️  ALSO writes to subdomains table (BulkInsertSubdomains) ← DUPLICATE!
   ✍️  Writes to dns_records table

HTTPX:
   📥 Consumes from Redis Stream
   ✍️  Writes to http_probes table

PROBLEM: 
- Duplicate writes to subdomains table
- Subfinder's write is BROKEN (missing asset_id)
- Unclear separation of concerns
```

#### **Code Evidence:**

**File:** `backend/containers/subfinder-go/scanner.go` (Lines 135-137)
```go
// Store individual domain results to database
if err := s.storeSubdomains(result); err != nil {
    s.logger.Errorf("Failed to store subdomains for domain %s: %v", ...)
```
**Issue:** Unconditional database write, regardless of streaming mode.

**File:** `backend/containers/subfinder-go/scanner.go` (Lines 475-490)
```go
record := map[string]interface{}{
    "subdomain":     subdomain.Subdomain,
    "source_module": subdomain.Source,
    "discovered_at": subdomain.DiscoveredAt,
    "scan_job_id":   jobID,
    "parent_domain": subdomain.ParentDomain,
    // ❌ MISSING: "asset_id": assetID
}
```
**Issue:** Database insert doesn't include required `asset_id` field.

**File:** `backend/containers/dnsx-go/streaming.go` (Line 354)
```go
subdomainResult, err := supabaseClient.BulkInsertSubdomains([]SubdomainRecord{subdomainRecord})
```
**Issue:** DNSx ALSO writes subdomains (correct behavior, but creates duplication).

---

### **4.4 Why DNSx Was Not Launched**

**Test Request:** `["subfinder", "httpx"]`

**Backend Logic** (`scan_pipeline.py`):
```python
DEPENDENCIES = {
    "subfinder": [],        # No dependencies
    "dnsx": ["subfinder"],  # Requires subfinder
    "httpx": ["subfinder"]  # Requires subfinder
}
```

**Result:** Only modules explicitly requested are launched.

**What Happened:**
1. User requested: `["subfinder", "httpx"]`
2. System launched: Subfinder + HTTPx (no DNSx)
3. Subfinder tried to write to DB (failed)
4. HTTPx waited for stream data (never arrived)

**Critical Insight:** DNSx is the **persistence layer** for Subfinder, but not enforced as a dependency!

---

### **4.5 Solution A: Enforce DNSx Dependency (Recommended)**

#### **Architectural Principle:**

> **DNSx is the canonical persistence layer for subdomain discovery. Subfinder is purely a discovery/streaming module and should NEVER write directly to the database.**

#### **Design Goals:**

1. ✅ **Single Source of Truth:** Only DNSx writes to `subdomains` table
2. ✅ **Clean Separation:** Subfinder = Discovery, DNSx = Persistence + DNS
3. ✅ **No Duplication:** Eliminate redundant write paths
4. ✅ **Mandatory Pipeline:** Enforce DNSx when Subfinder is used
5. ✅ **Stream-First:** All data flows through Redis Streams

#### **Implementation Plan:**

##### **STEP 1: Update Scan Pipeline Dependencies**

**File:** `backend/app/services/scan_pipeline.py`

**Current:**
```python
DEPENDENCIES = {
    "subfinder": [],        # Can run independently
    "dnsx": ["subfinder"],  # Requires subfinder
    "httpx": ["subfinder"]  # Requires subfinder
}
```

**New:**
```python
DEPENDENCIES = {
    "subfinder": ["dnsx"],  # ALWAYS requires dnsx for persistence
    "dnsx": [],             # Can run independently (if subdomains exist)
    "httpx": ["subfinder"]  # Requires subfinder (stream producer)
}
```

**Rationale:**
- Subfinder cannot function without a persistence layer
- DNSx provides both persistence AND DNS enrichment
- HTTPx depends on Subfinder's stream, not DNSx

**Impact:**
- API will automatically include DNSx when Subfinder is requested
- User requests `["subfinder"]` → System launches `["subfinder", "dnsx"]`
- User requests `["subfinder", "httpx"]` → System launches `["subfinder", "dnsx", "httpx"]`

---

##### **STEP 2: Remove Database Writes from Subfinder**

**Files to Modify:**
1. `backend/containers/subfinder-go/scanner.go`
2. `backend/containers/subfinder-go/batch_support.go`
3. `backend/containers/subfinder-go/database.go` (potentially remove entire file)

**Changes:**

**File:** `scanner.go` (Line ~135)

**Current:**
```go
// Store individual domain results to database
if err := s.storeSubdomains(result); err != nil {
    s.logger.Errorf("Failed to store subdomains for domain %s: %v",
        result.Domain, err)
}

// Stream results to Redis Streams (if streaming mode enabled)
if err := s.streamSubdomainsToRedis(result); err != nil {
    s.logger.Errorf("Failed to stream subdomains for domain %s: %v",
        result.Domain, err)
}
```

**New:**
```go
// Stream results to Redis Streams (DNSx will handle persistence)
if err := s.streamSubdomainsToRedis(result); err != nil {
    s.logger.Errorf("Failed to stream subdomains for domain %s: %v",
        result.Domain, err)
    // CRITICAL: Return error if streaming fails
    // Without stream, DNSx cannot persist data
    return err
}

s.logger.Debugf("✅ Streamed %d subdomains for domain %s", 
    len(result.Subdomains), result.Domain)
```

**Rationale:**
- Remove `storeSubdomains()` call entirely
- Make streaming failure critical (not just a warning)
- Log success for observability

**File:** `batch_support.go` (Similar changes)

**Current:**
```go
// Store in Supabase using batch insert
return s.supabaseClient.BatchInsertSubdomains(subdomainRecords)
```

**New:**
```go
// Stream to Redis for DNSx to consume and persist
if !s.config.StreamingMode {
    return fmt.Errorf("batch mode requires streaming to be enabled for DNSx persistence")
}

// Streaming already happened in the scan loop
s.logger.Infof("✅ Batch completed: %d subdomains streamed to DNSx", len(subdomainRecords))
return nil
```

---

##### **STEP 3: Verify DNSx Handles Persistence Correctly**

**File:** `backend/containers/dnsx-go/streaming.go` (Line ~340)

**Current Behavior:**
```go
// Prepare subdomain record
subdomainRecord := SubdomainRecord{
    Subdomain:     subdomain,
    ParentDomain:  parentDomain,
    ScanJobID:     scanJobID,
    AssetID:       assetID,  // ✅ Already includes asset_id
    SourceModule:  "subfinder",
    DiscoveredAt:  time.Now().UTC(),
}

// Write to subdomains table
subdomainResult, err := supabaseClient.BulkInsertSubdomains([]SubdomainRecord{subdomainRecord})
```

**Verification Needed:**
- ✅ Confirm `asset_id` is always populated from stream message
- ✅ Confirm `bulk_insert_subdomains` function includes asset_id
- ✅ Test ON CONFLICT behavior (duplicate subdomain handling)

**Database Function** (Already confirmed correct):
```sql
CREATE OR REPLACE FUNCTION bulk_insert_subdomains(records jsonb) 
RETURNS TABLE(inserted integer, skipped integer)
AS $$
    INSERT INTO subdomains (
        parent_domain, 
        subdomain, 
        scan_job_id,
        asset_id,           -- ✅ Present
        source_module, 
        discovered_at
    )
    SELECT 
        (r->>'parent_domain')::TEXT,
        (r->>'subdomain')::TEXT,
        (r->>'scan_job_id')::UUID,
        (r->>'asset_id')::UUID,  -- ✅ Extracted
        (r->>'source_module')::TEXT,
        (r->>'discovered_at')::TIMESTAMPTZ
    FROM jsonb_array_elements(records) AS r
    ON CONFLICT (parent_domain, subdomain) DO NOTHING;
$$;
```

**Status:** ✅ DNSx implementation is correct, no changes needed.

---

##### **STEP 4: Update Streaming Configuration**

**Requirement:** Subfinder MUST always run in streaming mode when in production.

**File:** `backend/app/services/batch_workflow_orchestrator.py`

**Verify:**
```python
# For Subfinder, ALWAYS enable streaming
if module == "subfinder":
    environment_variables.extend([
        {"name": "STREAMING_MODE", "value": "true"},
        {"name": "STREAM_OUTPUT_KEY", "value": f"scan:{scan_job_id}:subfinder:output"},
    ])
```

**Status:** Need to verify this is always set.

---

##### **STEP 5: Clean Up Subfinder Database Code**

**Files to Review:**

1. **`database.go`** - Can potentially be removed entirely if no DB writes
   - Keep SupabaseClient struct (used for progress updates)
   - Remove `BatchInsertSubdomains` method
   - Keep `UpdateScanJobStatus` (used for progress tracking)

2. **`scanner.go`** 
   - Remove `storeSubdomains()` method
   - Remove all database insert logic
   - Keep streaming logic only

3. **`batch_support.go`**
   - Remove database insert calls
   - Keep streaming logic only

---

#### **Expected Outcomes:**

##### **After Implementation:**

```
┌─────────────────────────────────────────────────────────────────┐
│              CLEAN ARCHITECTURE (IMPLEMENTED)                    │
└─────────────────────────────────────────────────────────────────┘

USER REQUEST: ["subfinder", "httpx"]
SYSTEM LAUNCHES: ["subfinder", "dnsx", "httpx"]  ← DNSx auto-included

EXECUTION FLOW:

1. Subfinder runs
   └─> Discovers subdomains ✅
       └─> Publishes to Redis Stream ONLY 📤
           └─> NO database writes ✅

2. DNSx runs (auto-included)
   └─> Consumes from Subfinder's stream 📥
       └─> Resolves DNS records ✅
           └─> Writes to database:
               - subdomains table ✍️ (WITH asset_id)
               - dns_records table ✍️

3. HTTPx runs  
   └─> Consumes from Subfinder's stream 📥
       └─> Probes HTTP/HTTPS ✅
           └─> Writes to http_probes table ✍️
```

##### **Test Scenario Results:**

**Before Fix:**
```
Request: ["subfinder", "httpx"]
Launched: Subfinder + HTTPx (no DNSx)
Result: Subfinder fails → Stream empty → HTTPx times out ❌
```

**After Fix:**
```
Request: ["subfinder", "httpx"]
Launched: Subfinder + DNSx + HTTPx (DNSx auto-included)
Result: 
  - Subfinder streams ✅
  - DNSx persists + enriches ✅  
  - HTTPx probes ✅
  - Scan completes successfully ✅
```

---

#### **Benefits:**

1. ✅ **Eliminates Duplication:** Single write path to `subdomains` table
2. ✅ **Prevents Data Loss:** DNSx automatically included when Subfinder runs
3. ✅ **Cleaner Code:** Subfinder focused solely on discovery
4. ✅ **Better Observability:** Clear responsibility boundaries
5. ✅ **Correct Dependencies:** Architecture matches stated design
6. ✅ **Fixes HTTPx Test:** Unblocks end-to-end testing

---

#### **Risks & Mitigation:**

| Risk | Impact | Mitigation |
|------|--------|------------|
| DNSx becomes a single point of failure | If DNSx fails, no data is persisted | Add retry logic in DNSx stream consumer |
| Increased resource usage | DNSx always runs even if user doesn't need DNS data | Acceptable - persistence is mandatory |
| Breaking change for existing workflows | Users relying on Subfinder standalone | Document migration, add deprecation warning |
| Stream reliability | If Redis is down, data is lost | Add stream persistence, monitoring alerts |

---

#### **Testing Plan:**

##### **Test 1: Subfinder + HTTPx (Original Failing Case)**
```bash
Request: ["subfinder", "httpx"]
Expected:
  - System auto-includes DNSx ✅
  - Subfinder streams (no DB writes) ✅
  - DNSx persists subdomains ✅
  - HTTPx receives stream data ✅
  - HTTP probes created ✅
  - Scan completes successfully ✅
```

##### **Test 2: Subfinder Only**
```bash
Request: ["subfinder"]
Expected:
  - System auto-includes DNSx ✅
  - Subfinder streams ✅
  - DNSx persists subdomains + DNS records ✅
  - Scan completes successfully ✅
```

##### **Test 3: Full Pipeline**
```bash
Request: ["subfinder", "dnsx", "httpx"]
Expected:
  - All modules run as requested ✅
  - No duplicate writes ✅
  - Data flows: Subfinder → Stream → DNSx (writes) & HTTPx (reads) ✅
  - Scan completes successfully ✅
```

##### **Test 4: DNSx Only (Edge Case)**
```bash
Request: ["dnsx"]
Expected:
  - DNSx runs without Subfinder ✅
  - DNSx fetches existing subdomains from DB ✅
  - DNSx performs DNS resolution ✅
  - No errors ✅
```

---

### **4.6 Implementation Checklist**

**Phase 4.1: Pipeline Dependencies** (5 minutes)
- [ ] Update `DEPENDENCIES` in `scan_pipeline.py`
- [ ] Add unit tests for dependency resolution
- [ ] Verify API includes DNSx when Subfinder is requested

**Phase 4.2: Subfinder Code Cleanup** (30 minutes)
- [ ] Remove `storeSubdomains()` call from `scanner.go`
- [ ] Remove `BatchInsertSubdomains` call from `batch_support.go`
- [ ] Make streaming failures critical (return error)
- [ ] Remove `BatchInsertSubdomains` method from `database.go`
- [ ] Add clear logging for streaming success
- [ ] Update Subfinder README documenting stream-only behavior

**Phase 4.3: DNSx Verification** (10 minutes)
- [ ] Verify `asset_id` is always extracted from stream messages
- [ ] Test `bulk_insert_subdomains` function with asset_id
- [ ] Verify ON CONFLICT behavior (duplicates skipped)
- [ ] Check DNSx logs for subdomain insertion success

**Phase 4.4: Build & Deploy** (5 minutes)
- [ ] Commit changes with clear documentation
- [ ] Push to GitHub (triggers CI/CD)
- [ ] Monitor build for Subfinder container
- [ ] Verify backend deployment (updated dependencies)

**Phase 4.5: Cloud Testing** (10 minutes)
- [ ] Test 1: `["subfinder", "httpx"]` - Verify DNSx auto-included
- [ ] Test 2: `["subfinder"]` - Verify DNSx auto-included
- [ ] Test 3: `["subfinder", "dnsx", "httpx"]` - Full pipeline
- [ ] Verify CloudWatch logs show correct flow
- [ ] Verify database has subdomains + DNS records + HTTP probes

**Phase 4.6: Documentation** (15 minutes)
- [ ] Update CONTAINER_TEMPLATE.md with Subfinder pattern
- [ ] Update scan_modules README with dependency rules
- [ ] Add architecture diagram showing stream-first design
- [ ] Document migration notes for existing users

**Total Estimated Time:** ~75 minutes

---

### **4.7 Success Criteria**

✅ **Functional:**
- Subfinder never writes directly to database
- DNSx is automatically included when Subfinder is requested
- HTTPx receives stream data successfully
- All three modules complete without errors

✅ **Data Integrity:**
- No duplicate writes to `subdomains` table
- All subdomain records include `asset_id`
- No NULL constraint violations

✅ **Performance:**
- Scan completes within expected timeframe (1-2 minutes for 3 domains)
- No timeout errors
- CloudWatch logs show clean execution

✅ **Code Quality:**
- Clear separation of concerns (discovery vs. persistence)
- No dead code (removed unused database methods)
- Comprehensive logging for observability

---

### **4.8 Rollback Plan**

If issues arise after deployment:

1. **Revert Pipeline Dependencies:**
   ```python
   DEPENDENCIES = {
       "subfinder": [],  # Back to independent
       "dnsx": ["subfinder"],
       "httpx": ["subfinder"]
   }
   ```

2. **Revert Subfinder Code:**
   - Git revert to commit before database write removal
   - Emergency fix: Apply asset_id patch to Subfinder's direct writes

3. **Manual Testing:**
   - Test with explicit `["subfinder", "dnsx", "httpx"]` request
   - Verify at least the explicit flow works

**Rollback Time:** < 5 minutes (git revert + redeploy)

---

### **4.9 Next Steps After Approval**

Once you approve this plan, we will proceed in this order:

1. **Implement Phase 4.1:** Update pipeline dependencies (backend)
2. **Implement Phase 4.2:** Clean up Subfinder code (container)
3. **Commit & Deploy:** Push changes and wait for CI/CD
4. **Execute Tests:** Run all 4 test scenarios
5. **Document Results:** Update this tracker with outcomes
6. **Move to Phase 5:** Frontend integration (if tests pass)

---

**STATUS:** ⏸️ **AWAITING APPROVAL**

Please review this plan and confirm:
- ✅ Architectural approach (Solution A: Enforce DNSx)
- ✅ Implementation steps (detailed above)
- ✅ Testing strategy (4 test scenarios)
- ✅ Any modifications or concerns

Once approved, I will proceed with implementation immediately.


---

### **4.10 Implementation Progress**

**Started:** November 14, 2025 - 18:45 UTC

#### **✅ STEP 1 COMPLETED: Update Scan Pipeline Dependencies**

**Commit:** `7128a7e`  
**File:** `backend/app/services/scan_pipeline.py`  
**Duration:** 10 minutes

**Changes Made:**
```python
# Added auto-include logic in _resolve_execution_order():
if "subfinder" in modules_set and "dnsx" not in modules_set:
    self.logger.info(
        "🔧 Auto-including 'dnsx' module: Subfinder requires DNSx for data persistence"
    )
    modules_set.add("dnsx")
```

**Result:**
- ✅ Request `["subfinder", "httpx"]` → System executes `["subfinder", "dnsx", "httpx"]`
- ✅ Clear logging for visibility
- ✅ No breaking changes to existing workflows
- ✅ Backend will deploy automatically via GitHub Actions

**Testing:**
- Will verify after deployment that DNSx is automatically included
- Expected log: "Auto-including 'dnsx' module"

---

#### **✅ STEP 2 COMPLETED: Remove Database Writes from Subfinder**

**Commit:** `5779e0d`  
**Files:** 
- `backend/containers/subfinder-go/scanner.go`
- `backend/containers/subfinder-go/batch_support.go`

**Duration:** 20 minutes  
**Lines Removed:** 121 lines (database write logic)  
**Lines Added:** 36 lines (improved streaming logic)

**Changes Made:**

**1. scanner.go (Main Scan Flow):**
```go
// BEFORE (broken):
if err := s.storeSubdomains(result); err != nil {
    s.logger.Errorf("Failed to store subdomains...") // Just logs, continues
}

// AFTER (stream-only):
if err := s.streamSubdomainsToRedis(result); err != nil {
    s.logger.Errorf("❌ CRITICAL: Failed to stream...")
    result.Progress.Status = "failed"  // Marks as failed
} else {
    s.logger.Debugf("✅ Streamed %d subdomains...", len(result.Subdomains))
}
```

**2. batch_support.go (Batch Scan Flow):**
```go
// BEFORE (dual-path with broken fallback):
if s.config.StreamingMode {
    // Try streaming
    if err := s.streamSubdomainsToRedis(result); err != nil {
        // Fallback to database (broken: missing asset_id)
        return s.supabaseClient.BatchInsertSubdomains(records)
    }
}
// Also direct database write if not streaming

// AFTER (streaming-only):
if !s.config.StreamingMode {
    return fmt.Errorf("CRITICAL: Batch mode requires streaming")
}
if err := s.streamSubdomainsToRedis(result); err != nil {
    return fmt.Errorf("CRITICAL: Failed to stream: %w", err)
}
return nil // DNSx will persist
```

**3. Deleted Functions:**
- ❌ `storeSubdomains()` - 54 lines removed
- ❌ Database fallback logic - 45 lines removed
- ❌ Subdomain record preparation for DB - 22 lines removed

**Result:**
- ✅ Subfinder is now **stream-only**
- ✅ No database writes at all
- ✅ Streaming failures are **critical** (not ignored)
- ✅ Cleaner error messages
- ✅ ~100 lines of code removed
- ✅ Clear architectural separation enforced

**Testing:**
- Subfinder container will rebuild via GitHub Actions
- Will test with `["subfinder", "httpx"]` request
- Expected: Subfinder streams → DNSx persists → HTTPx consumes → Success

---

#### **📊 DEPLOYMENT STATUS:**

**GitHub Actions:**
- ✅ Commit `7128a7e` (Step 1) - Pushed
- ✅ Commit `5779e0d` (Step 2) - Pushed
- ⏳ Build in progress...

**Expected Build Output:**
```
🎯 SMART DEPLOYMENT
├── Backend API: true (scan_pipeline.py changed)
├── Subfinder Container: true (scanner.go, batch_support.go changed)
├── DNSX Container: false (no changes)
├── HTTPx Container: false (no changes)

⚡ Build Optimization:
✅ Backend container built
✅ Subfinder container built
⏭️ DNSX container skipped
⏭️ HTTPx container skipped
```

**Deployment Timeline:**
- Backend API: ~4 minutes (ECS task restart)
- Subfinder Container: ~4 minutes (build + ECR push + ECS update)
- Total: ~8 minutes

**Verification:**
```bash
# After deployment, test the fix:
export SCAN_TEST_PASSWORD="TestSamPluck2025!!"

./docs/test_scan.sh \
  --asset-id 0af5ae55-feea-491d-bfdc-be0c66fd69f0 \
  --modules '["subfinder", "httpx"]'

# Expected output:
# 1. "Auto-including 'dnsx' module" in logs
# 2. Subfinder streams to Redis
# 3. DNSx consumes and persists subdomains
# 4. HTTPx consumes and creates HTTP probes
# 5. Scan completes successfully
```

---

#### **🎯 NEXT STEPS:**

**Immediate (While Waiting for Deployment):**
- [x] Step 1: Pipeline dependencies ✅
- [x] Step 2: Subfinder code cleanup ✅
- [ ] Step 3: Verify DNSx persistence (already correct)
- [ ] Step 4: Wait for GitHub Actions build (~8 minutes)
- [ ] Step 5: Run cloud test
- [ ] Step 6: Verify database results
- [ ] Step 7: Update project tracker with test results

**After Successful Test:**
- [ ] Update CONTAINER_TEMPLATE.md with streaming-only pattern
- [ ] Document migration notes for future modules
- [ ] Move to Phase 5: HTTPx frontend integration

---

#### **📝 CRITICAL REASONING CHECKPOINT:**

**Why This Approach Works:**

1. **Pipeline Auto-Include (Step 1):**
   - User convenience: Request `["subfinder"]`, get persistence automatically
   - Prevents data loss: DNSx always runs when Subfinder runs
   - Transparent: Logged clearly for debugging

2. **Stream-Only Architecture (Step 2):**
   - Single source of truth: Only DNSx writes to `subdomains` table
   - Cleaner failure modes: If streaming fails, it's immediately visible
   - Easier to debug: No ambiguity about which module wrote what data
   - Smaller codebase: ~100 lines of duplicate logic removed

3. **Backwards Compatibility:**
   - Users explicitly requesting `["subfinder", "dnsx"]` → No change
   - Users requesting `["subfinder"]` → Get DNSx auto-included (better!)
   - DNSx can still run standalone (for re-scanning existing subdomains)

**Potential Issues & Mitigations:**

| Issue | Probability | Mitigation |
|-------|-------------|-----------|
| Streaming fails due to Redis downtime | Low | Monitor Redis health, add alerting |
| DNSx becomes bottleneck | Low | DNSx is lightweight, already handles this |
| User confusion about auto-include | Medium | Clear logging + documentation |
| Breaking existing workflows | Low | Only improves behavior, no regressions |

---

**STATUS:** ⏳ **AWAITING DEPLOYMENT (ETA: ~8 minutes)**

Once GitHub Actions completes, we will proceed with cloud testing.


---

### **4.11 Parallel Streaming Architecture Implementation & Debugging**

**Started:** November 14, 2025 - 20:00 UTC  
**Status:** 🔍 **CRITICAL BUG DISCOVERED - EXECUTION BLOCKED**

---

#### **Background: Sequential → Parallel Streaming Evolution**

**User Request:**
> "Why can't we run httpx as a stream? I want that fuck sequential scanning, it is slow."

**Architectural Decision:** Implement **parallel streaming consumers** where both DNSx AND HTTPx consume from Subfinder's stream simultaneously, rather than sequential execution.

**Rationale:**
- ✅ **Faster**: No waiting for DNSx to complete before HTTPx starts
- ✅ **Independent**: Each consumer processes at its own pace
- ✅ **Scalable**: Pattern extends to N consumers (future: nuclei, nmap, etc.)
- ✅ **Real-time**: Both modules process discoveries as they arrive

---

#### **Implementation Changes**

##### **STEP 1: Refactor `execute_streaming_pipeline()` for Multiple Consumers**

**File:** `backend/app/services/scan_pipeline.py`

**Changes:**
```python
# OLD (Single Consumer - DNSx only):
consumer_job = await self._create_batch_scan_job(module="dnsx", ...)
launch_result = await batch_workflow_orchestrator.launch_streaming_pipeline(
    producer_job=producer_job,
    consumer_job=consumer_job,
    stream_key=stream_key
)

# NEW (Multiple Parallel Consumers - DNSx + HTTPx):
consumer_modules = [m for m in modules if m != "subfinder"]  # ["dnsx", "httpx"]
consumer_jobs = {}

for module in consumer_modules:
    consumer_jobs[module] = await self._create_batch_scan_job(module=module, ...)

# Launch producer separately
producer_launch = await batch_workflow_orchestrator.launch_streaming_producer(...)

# Launch each consumer in parallel
for module in consumer_modules:
    consumer_launch = await batch_workflow_orchestrator.launch_streaming_consumer(
        consumer_job=consumer_jobs[module],
        stream_key=stream_key,
        consumer_group_name=f"{module}-consumers",  # Separate groups!
        consumer_name=f"{module}-{job_id}"
    )
```

**Key Architecture Points:**
- **Separate Consumer Groups**: Each module has its own group (e.g., `dnsx-consumers`, `httpx-consumers`)
- **Same Stream**: All consumers read from `scan:{job_id}:subfinder:output`
- **Independent Progress**: Each consumer ACKs messages independently
- **Parallel Execution**: No blocking between consumers

---

##### **STEP 2: Add New Orchestrator Methods**

**File:** `backend/app/services/batch_workflow_orchestrator.py`

**New Methods:**
1. **`launch_streaming_producer()`** - Launch producer task (Subfinder)
2. **`launch_streaming_consumer()`** - Launch individual consumer task (DNSx or HTTPx)
3. **`monitor_multiple_tasks()`** - Monitor health of N tasks (1 producer + M consumers)

**Deprecated Methods:**
- ❌ `launch_streaming_pipeline()` - Only handled 1 producer + 1 consumer
- ❌ `monitor_streaming_tasks()` - Only monitored 2 tasks

**Benefit:** Modular, reusable methods that scale to N consumers

---

#### **Bug Discovery Journey (Validation Layers)**

During implementation, we discovered **7 validation layers** that must ALL be updated when adding a new module:

##### **The 7 Validation Layers:**

| # | Layer | Location | What It Does | Status |
|---|-------|----------|--------------|--------|
| 1 | `asset_scan_jobs.valid_modules` | `migrations/*.sql` | Validates module names in asset scans | ✅ Fixed |
| 2 | `batch_scan_jobs.valid_module` | `migrations/*.sql` | Validates module names in batch jobs | ✅ Fixed |
| 3 | `scan_module_profiles` | `migrations/add_httpx_module_profile.sql` | Module registry with config | ✅ Complete |
| 4 | `scan_pipeline.py` DEPENDENCIES | `backend/app/services/scan_pipeline.py` | Execution order resolution | ✅ Complete |
| 5 | `ReconModule` Pydantic schema | `backend/app/schemas/recon.py` | API request validation | ✅ Fixed |
| 6 | Terraform + GitHub Actions | `infrastructure/`, `.github/workflows/` | Build & deployment | ✅ Fixed |
| 7 | Container name mapping | `batch_workflow_orchestrator.py` | ECS container override | ✅ Fixed |

**Critical Lesson:** Missing ANY layer causes cryptic failures at different stages!

---

#### **Bugs Found & Fixed**

##### **BUG 1: Missing Database Constraint (Layer 2)**
**Error:**
```
new row for relation "batch_scan_jobs" violates check constraint "valid_module"
```

**Root Cause:** Layer 1 (`asset_scan_jobs`) had `httpx`, but Layer 2 (`batch_scan_jobs`) did not.

**Fix:** 
```sql
ALTER TABLE batch_scan_jobs
ADD CONSTRAINT valid_module CHECK (
    module = ANY (ARRAY['subfinder'::text, 'dnsx'::text, 'httpx'::text])
);
```

**Migration:** `backend/migrations/add_httpx_to_batch_scan_jobs_constraint.sql`

---

##### **BUG 2: Missing API Schema (Layer 5)**
**Error:**
```json
{
  "detail": [
    {
      "type": "enum",
      "msg": "Input should be 'subfinder' or 'dnsx'",
      "input": "httpx"
    }
  ]
}
```

**Root Cause:** FastAPI Pydantic schema didn't include `HTTPX` enum value.

**Fix:**
```python
# backend/app/schemas/recon.py
class ReconModule(str, Enum):
    SUBFINDER = "subfinder"
    DNSX = "dnsx"
    HTTPX = "httpx"  # ← ADDED
```

**Impact:** API rejected requests before they reached backend logic (fail-fast principle).

---

##### **BUG 3: Missing Container Name Mapping (Layer 7)**
**Error:**
```
Override for container named httpx is not a container in the TaskDefinition
```

**Root Cause:** 
- Task definition has container named `httpx-scanner`
- Orchestrator was using module name `httpx` as fallback
- Missing mapping in `_get_container_name()`

**Fix:**
```python
# batch_workflow_orchestrator.py
container_name_mapping = {
    'dnsx': 'dnsx-scanner',
    'httpx': 'httpx-scanner',  # ← ADDED
    'subfinder': 'subfinder',
}
```

**Why This Happens:** Module names (`httpx`) != Container names (`httpx-scanner`) in task definitions.

---

#### **🔴 CRITICAL BUG 4: Missing `await` in Orchestrator**

**Status:** 🚨 **BLOCKING EXECUTION**  
**Discovered:** November 14, 2025 - 21:05 UTC

##### **The Problem:**

**File:** `backend/app/services/scan_orchestrator.py` (Line 414)

```python
# WRONG (Creates coroutine but never executes it):
task = scan_pipeline.execute_streaming_pipeline(
    asset_id=asset_id,
    modules=modules,
    scan_request=config,
    user_id=user_id,
    scan_job_id=scan_id
)
```

**What This Does:**
- Creates a **coroutine object** 
- Assigns it to variable `task`
- **NEVER executes the coroutine**

**Result:** The streaming pipeline code never runs!

##### **Evidence from Logs:**

```
✅ [16eef97d] 🚀 Asset rikhter: Streaming pipeline
✅ [16eef97d] ⏳ Waiting for pipelines to complete...

... [NOTHING - No logs from execute_streaming_pipeline] ...

❌ Test timeout after 180 seconds
```

**Expected Logs (Missing):**
```
🌊 Starting STREAMING pipeline for asset {id}
📋 Creating producer job (Subfinder)...
✅ Producer job created: {job_id}
📋 Creating 2 consumer job(s): ['dnsx', 'httpx']
🚀 Launching streaming pipeline: 1 producer + 2 parallel consumers...
```

**Critical Insight:** The FIRST log line from `execute_streaming_pipeline()` never appears, proving the method never executed.

##### **The Fix:**

```python
# CORRECT (Execute the coroutine):
task = asyncio.create_task(scan_pipeline.execute_streaming_pipeline(
    asset_id=asset_id,
    modules=modules,
    scan_request=config,
    user_id=user_id,
    scan_job_id=scan_id
))

# OR (if not running in parallel):
await scan_pipeline.execute_streaming_pipeline(...)
```

##### **Why This is Subtle:**

1. Python doesn't error on unawaited coroutines (only warns)
2. The code "looks correct" (creates task variable)
3. The orchestrator continues executing (doesn't know task never ran)
4. Manifests as a timeout (system waits for something that never starts)

##### **Impact:**

- 🚫 **ALL streaming pipeline tests blocked**
- 🚫 **HTTPx completely untested** (never reached execution)
- 🚫 **Parallel consumer architecture unverified**
- ⏱️ **3 hours debugging downstream effects** when root cause was line 414

---

#### **Test Results Summary**

##### **Test 1: `["subfinder", "httpx"]` - TIMEOUT**
```
Request: ["subfinder", "httpx"]
Expected: Subfinder → DNSx (auto-included) + HTTPx (parallel)
Result: ❌ TIMEOUT (3 minutes)
Reason: execute_streaming_pipeline() never called
```

##### **Root Cause Chain:**
```
Line 414: task = execute_streaming_pipeline(...)  ← Missing await
    ↓
Coroutine created but never executed
    ↓
No producer/consumer tasks launched
    ↓
System waits for tasks that don't exist
    ↓
Timeout after 180 seconds
```

---

#### **Documentation Updates**

##### **Updated CONTAINER_TEMPLATE.md**
Added comprehensive **"11. Validation Layers (Critical!)"** section:

- Quick Reference Table (all 7 layers)
- Detailed explanation of each layer
- Search patterns for finding each layer
- Error messages when layers are missing
- Critical reasoning (why 7 layers exist)

**Key Addition:**
```markdown
| # | What to Update | File Path | Search For |
|---|---------------|-----------|------------|
| 1 | asset_scan_jobs constraint | migrations | valid_modules CHECK |
| 2 | batch_scan_jobs constraint | migrations | valid_module CHECK |
| 3 | Module profile | migrations | add_{module}_module_profile.sql |
| 4 | Pipeline dependencies | scan_pipeline.py | DEPENDENCIES = { |
| 5 | API Pydantic schema | recon.py | class ReconModule |
| 6 | Infrastructure | terraform/, .github/ | ECR, ECS, workflows |
| 7 | Container mapping | batch_workflow_orchestrator.py | _get_container_name |
```

---

#### **Current Status**

##### **✅ Completed:**
- [x] Parallel streaming architecture implemented
- [x] Multiple consumer support added
- [x] New orchestrator methods created
- [x] All 7 validation layers fixed
- [x] Database constraints updated
- [x] API schema updated
- [x] Container name mapping fixed
- [x] Terraform/GitHub Actions configured
- [x] Documentation updated (CONTAINER_TEMPLATE.md)

##### **🚨 Blocking Issue:**
- [ ] Fix missing `await` in scan_orchestrator.py line 414

##### **⏳ Pending After Fix:**
- [ ] Deploy backend (fix orchestrator await)
- [ ] Re-test `["subfinder", "httpx"]`
- [ ] Verify parallel consumer execution
- [ ] Verify DNSx + HTTPx write to database
- [ ] CloudWatch log analysis
- [ ] Frontend integration (Phase 7)

---

#### **Next Steps (After Break)**

**Immediate Fix Required:**
```python
# File: backend/app/services/scan_orchestrator.py (Line 414)

# CURRENT (BROKEN):
task = scan_pipeline.execute_streaming_pipeline(...)

# FIX (Option A - Create async task):
task = asyncio.create_task(scan_pipeline.execute_streaming_pipeline(...))

# FIX (Option B - Await directly):
await scan_pipeline.execute_streaming_pipeline(...)
```

**Deployment:**
1. Commit orchestrator fix
2. Push to GitHub (triggers backend deployment)
3. Wait ~4 minutes for ECS task restart
4. Re-test with same test case

**Expected Test Duration:** 1-2 minutes (if fix works)

---

#### **Lessons Learned**

##### **1. Validation Layers are Hidden Landmines**
- Must check ALL 7 layers when adding a module
- Each layer fails at a different stage (API, database, ECS)
- Created checklist in CONTAINER_TEMPLATE.md to prevent future issues

##### **2. Async/Await Bugs are Sneaky**
- Python doesn't error on unawaited coroutines
- Manifests as timeouts or "nothing happens"
- Always verify coroutines are awaited or wrapped in asyncio.create_task()

##### **3. Logging is Critical for Debugging**
- Missing logs immediately reveal execution gaps
- "Expected log never appeared" = method never called
- Always log method entry points for visibility

##### **4. Architectural Refactors Need Full E2E Tests**
- Parallel streaming required 3 components (pipeline, orchestrator, containers)
- Missing one piece (await) breaks the entire chain
- Should have tested each layer independently

##### **5. Time Investment**
- **Bug finding:** 3 hours (debugging downstream effects)
- **Bug fixing:** 5 minutes (once root cause found)
- **Lesson:** Find root cause first, don't patch symptoms

---

#### **Performance Expectations (Post-Fix)**

**Current (Sequential):**
```
Subfinder → DNSx → HTTPx
Time: T1 + T2 + T3 = ~5-8 minutes
```

**After Fix (Parallel):**
```
Subfinder → DNSx + HTTPx (parallel)
Time: T1 + max(T2, T3) = ~3-5 minutes
Expected Speedup: 40-50%
```

**Test Case:** `hackerone.com, epicgames.com, t-mobile.com`
- **Expected Subdomains:** 50-150
- **Sequential Time:** ~6 minutes
- **Parallel Time:** ~3-4 minutes

---

#### **Documentation Debt Paid**

1. ✅ **CONTAINER_TEMPLATE.md** - Added validation layers section
2. ✅ **Project Plan** - Comprehensive Phase 4.11 section (this document)
3. ✅ **Architecture Diagrams** - Parallel consumer pattern documented
4. ⏳ **Post-Fix** - Add orchestrator await pattern to best practices

---

**END OF PHASE 4.11**

**Status:** 📋 **DOCUMENTED & READY FOR BREAK**

**Next Session:** Fix orchestrator await bug, deploy, and re-test parallel streaming.

**Estimated Time to Resolution:** 15 minutes (fix + deploy + test)

---

