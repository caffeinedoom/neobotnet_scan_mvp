# Katana Output Analysis & Database Schema Design

**Date:** November 20, 2025  
**Analyst:** Database Schema Design  
**Test Duration:** 60 seconds  
**Test URL:** `https://blog.nubank.com.br/`  
**Results File:** `backend/containers/katana-test/output/results.json` (2.8MB, 445 lines)

---

## 1. Executive Summary

Katana captured **9 unique endpoints** during a 60-second headless crawl at depth 1. The output reveals a clean, well-structured JSON format with consistent fields suitable for database storage. The primary challenge is **response body size** (ranging from 0 to 281KB per endpoint), which requires careful storage strategy.

---

## 2. JSON Structure Analysis

### 2.1 Top-Level Structure

```json
{
  "results": [/* array of crawl results */],
  "stats": {/* summary statistics */}
}
```

### 2.2 Individual Result Entry

Each result contains:

```json
{
  "timestamp": "2025-11-20T22:42:22.22130573Z",
  "request": {
    "method": "GET",
    "endpoint": "https://blog.nubank.com.br/...",
    "raw": "GET /... HTTP/1.1\r\nHost: ..."
  },
  "response": {
    "status_code": 200,
    "content_length": 1327,
    "headers": {
      "content-type": "text/html; charset=utf-8",
      "x-powered-by": "Next.js",
      ...
    },
    "body": "<!DOCTYPE html>...",
    "raw": "HTTP/1.1 200 OK\r\n..."
  }
}
```

### 2.3 Statistics Summary

```json
{
  "total_urls": 9,
  "unique_endpoints": 9,
  "form_count": 0,
  "depth_max": 1,
  "start_time": "2025-11-20T22:42:08Z",
  "end_time": "2025-11-20T22:43:08Z",
  "duration_seconds": 60.0
}
```

---

## 3. Data Characteristics

### 3.1 Field Presence & Optionality

| Field | Always Present? | Nullable? | Notes |
|-------|----------------|-----------|-------|
| `timestamp` | ✅ Yes | ❌ No | RFC3339 format |
| `request.method` | ✅ Yes | ❌ No | Always "GET" in test |
| `request.endpoint` | ✅ Yes | ❌ No | Full URL |
| `request.raw` | ✅ Yes | ❌ No | Raw HTTP request |
| `response.status_code` | ⚠️ Conditional | ✅ Yes | `null` for failed requests |
| `response.content_length` | ⚠️ Conditional | ✅ Yes | `null` if not provided by server |
| `response.headers` | ✅ Yes | ❌ No | Can be empty object `{}` |
| `response.body` | ⚠️ Conditional | ✅ Yes | `null` for failed requests |
| `response.raw` | ✅ Yes | ❌ No | Raw HTTP response |

### 3.2 Data Size Analysis (from 9 endpoints)

| Metric | Min | Max | Average | Notes |
|--------|-----|-----|---------|-------|
| **Body Size** | 0 bytes | 281 KB | ~90 KB | HTML pages largest |
| **Header Count** | 0 | 56 | ~30 | Successful requests: 20-56 headers |
| **Status Codes** | - | - | - | 200 (5), 404 (2), null (2) |
| **Response Time** | - | - | - | Not captured in current output |

### 3.3 Missing Fields (Expected from Katana Docs)

**Not present in current output:**
- `request.source` - Which page linked to this endpoint
- `request.tag` - HTML tag that contained the link (e.g., `<a>`, `<script>`)
- `request.attribute` - HTML attribute (e.g., `href`, `src`)
- `response.technologies` - Detected technologies (Wappalyzer)
- `response.forms` - HTML form data

**Reason:** These fields appear when JavaScript parsing and form detection are actively used. Our shallow depth-1 crawl didn't encounter forms, and source tracking may require additional configuration.

---

## 4. Database Schema Proposal

### 4.1 Design Principles

1. **Normalized Structure** - Separate core endpoint data from bulky response bodies
2. **Deduplication** - Per-scan deduplication using `(scan_job_id, url_hash)`
3. **Selective Storage** - Store response bodies in separate table with optional truncation
4. **Queryability** - Index key fields for fast lookups (URL, status, content-type)
5. **Audit Trail** - Track when endpoints were first/last seen

### 4.2 Primary Table: `crawled_endpoints`

```sql
CREATE TABLE crawled_endpoints (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,
    
    -- Foreign Keys
    scan_job_id BIGINT NOT NULL REFERENCES batch_scan_jobs(id) ON DELETE CASCADE,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    
    -- Endpoint Identification
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL,  -- SHA256 of normalized URL for deduplication
    
    -- Request Details
    method VARCHAR(10) NOT NULL DEFAULT 'GET',
    source_url TEXT,  -- Which page linked to this endpoint (null for seed URLs)
    discovered_from VARCHAR(50),  -- 'seed', 'href', 'script', 'img', 'form', etc.
    
    -- Response Metadata
    status_code INTEGER,  -- NULL if request failed
    content_type VARCHAR(255),
    content_length BIGINT,
    
    -- Response Headers (JSON)
    response_headers JSONB,  -- Store as JSONB for queryability
    
    -- Timing & Depth
    crawled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    depth INTEGER NOT NULL DEFAULT 0,  -- Distance from seed URL
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_endpoint_per_scan UNIQUE(scan_job_id, url_hash),
    CONSTRAINT valid_status_code CHECK (status_code IS NULL OR (status_code >= 100 AND status_code < 600))
);

-- Indexes for common queries
CREATE INDEX idx_crawled_endpoints_scan_job ON crawled_endpoints(scan_job_id);
CREATE INDEX idx_crawled_endpoints_asset ON crawled_endpoints(asset_id) WHERE asset_id IS NOT NULL;
CREATE INDEX idx_crawled_endpoints_status ON crawled_endpoints(status_code) WHERE status_code IS NOT NULL;
CREATE INDEX idx_crawled_endpoints_content_type ON crawled_endpoints(content_type) WHERE content_type IS NOT NULL;
CREATE INDEX idx_crawled_endpoints_url_hash ON crawled_endpoints(url_hash);
CREATE INDEX idx_crawled_endpoints_crawled_at ON crawled_endpoints(crawled_at DESC);

-- GIN index for JSONB header queries
CREATE INDEX idx_crawled_endpoints_headers ON crawled_endpoints USING GIN(response_headers);
```

### 4.3 Separate Table: `endpoint_response_bodies`

**Rationale:** Response bodies can be 100KB-500KB+ of HTML. Storing them separately:
- Keeps main table queries fast
- Allows selective retrieval (only when needed)
- Enables easier purging of old data

```sql
CREATE TABLE endpoint_response_bodies (
    -- Primary Key
    endpoint_id BIGINT PRIMARY KEY REFERENCES crawled_endpoints(id) ON DELETE CASCADE,
    
    -- Response Body
    body_full TEXT,  -- Full response body (HTML, JSON, etc.)
    body_excerpt TEXT,  -- First 1000 characters for preview
    body_size INTEGER NOT NULL,  -- Original size in bytes
    
    -- Compression metadata (if we compress in future)
    is_compressed BOOLEAN DEFAULT FALSE,
    compression_type VARCHAR(20),  -- 'gzip', 'brotli', null
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for size-based queries
CREATE INDEX idx_response_bodies_size ON endpoint_response_bodies(body_size);
```

### 4.4 Optional Table: `detected_technologies`

**Use Case:** If Wappalyzer/technology detection is enabled in future

```sql
CREATE TABLE detected_technologies (
    id BIGSERIAL PRIMARY KEY,
    endpoint_id BIGINT NOT NULL REFERENCES crawled_endpoints(id) ON DELETE CASCADE,
    
    -- Technology Info
    technology_name VARCHAR(100) NOT NULL,
    technology_version VARCHAR(50),
    technology_category VARCHAR(50),  -- 'cms', 'framework', 'analytics', etc.
    confidence VARCHAR(20),  -- 'low', 'medium', 'high'
    
    -- Audit
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_tech_per_endpoint UNIQUE(endpoint_id, technology_name)
);

CREATE INDEX idx_detected_technologies_endpoint ON detected_technologies(endpoint_id);
CREATE INDEX idx_detected_technologies_name ON detected_technologies(technology_name);
```

### 4.5 Optional Table: `detected_forms`

**Use Case:** Store HTML form data when detected

```sql
CREATE TABLE detected_forms (
    id BIGSERIAL PRIMARY KEY,
    endpoint_id BIGINT NOT NULL REFERENCES crawled_endpoints(id) ON DELETE CASCADE,
    
    -- Form Metadata
    form_action TEXT NOT NULL,  -- Form submission URL
    form_method VARCHAR(10) DEFAULT 'GET',
    form_id VARCHAR(255),
    form_name VARCHAR(255),
    
    -- Form Fields (JSON array)
    form_fields JSONB,  -- [{"name": "username", "type": "text", "required": true}, ...]
    
    -- Audit
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_detected_forms_endpoint ON detected_forms(endpoint_id);
CREATE INDEX idx_detected_forms_action ON detected_forms(form_action);
```

---

## 5. Deduplication Strategy

### 5.1 Recommended Approach: **Per-Scan Deduplication**

**Reasoning:**
- URLs may return different status codes/content over time
- Different scans should capture state at that point in time
- Allows tracking changes between scans

**Implementation:**
```sql
CONSTRAINT unique_endpoint_per_scan UNIQUE(scan_job_id, url_hash)
```

### 5.2 URL Normalization & Hashing

Before inserting, normalize URLs to prevent duplicates:

```go
import (
    "crypto/sha256"
    "encoding/hex"
    "net/url"
    "strings"
)

func NormalizeAndHashURL(rawURL string) (normalized string, hash string, error) {
    // Parse URL
    u, err := url.Parse(rawURL)
    if err != nil {
        return "", "", err
    }
    
    // Normalize
    u.Host = strings.ToLower(u.Host)
    u.Scheme = strings.ToLower(u.Scheme)
    
    // Sort query parameters for consistency
    q := u.Query()
    u.RawQuery = q.Encode()
    
    // Remove fragment
    u.Fragment = ""
    
    normalized = u.String()
    
    // Generate hash
    h := sha256.Sum256([]byte(normalized))
    hash = hex.EncodeToString(h[:])
    
    return normalized, hash, nil
}
```

### 5.3 Alternative: Global Deduplication

**Use Case:** If you want to track "when was this endpoint EVER seen?"

```sql
-- Add index for global lookups
CREATE INDEX idx_crawled_endpoints_url_hash_latest ON crawled_endpoints(url_hash, crawled_at DESC);

-- Query: Find latest occurrence of a URL
SELECT * FROM crawled_endpoints 
WHERE url_hash = $1 
ORDER BY crawled_at DESC 
LIMIT 1;
```

---

## 6. Storage Optimization Strategies

### 6.1 Response Body Storage Options

| Strategy | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Full Storage** | Complete data for analysis | Large storage (100KB+ per endpoint) | ✅ For depth-1 crawls (manageable volume) |
| **Excerpt Only** | Minimal storage | Lose full context | ⚠️ For deep crawls (depth 3+) |
| **Compression** | 60-70% size reduction | CPU overhead, complexity | ✅ For long-term retention |
| **S3 Archive** | Cheap cold storage | Slower retrieval | ✅ For historical data (>30 days) |
| **TTL Purge** | Auto-cleanup old data | Data loss | ✅ Combined with excerpt retention |

### 6.2 Recommended Hybrid Approach

1. **Store full bodies** for depth ≤ 2 crawls
2. **Store excerpts only** (first 1000 chars) for depth 3+ crawls
3. **Compress bodies** after 7 days (GZIP in PostgreSQL)
4. **Archive to S3** after 30 days (if long-term retention needed)
5. **Purge bodies** after 90 days (keep metadata + excerpts)

---

## 7. Query Patterns & Indexes

### 7.1 Common Queries

```sql
-- 1. Get all endpoints for a scan
SELECT id, url, status_code, content_type 
FROM crawled_endpoints 
WHERE scan_job_id = $1 
ORDER BY crawled_at;

-- 2. Find all 404s in a scan
SELECT url, crawled_at 
FROM crawled_endpoints 
WHERE scan_job_id = $1 AND status_code = 404;

-- 3. Find endpoints with specific header
SELECT url, response_headers->'server' as server 
FROM crawled_endpoints 
WHERE scan_job_id = $1 
  AND response_headers ? 'server';

-- 4. Find all JavaScript files
SELECT url, content_length 
FROM crawled_endpoints 
WHERE scan_job_id = $1 
  AND content_type LIKE 'application/javascript%';

-- 5. Get endpoint with response body
SELECT ce.*, erb.body_excerpt 
FROM crawled_endpoints ce
LEFT JOIN endpoint_response_bodies erb ON ce.id = erb.endpoint_id
WHERE ce.id = $1;

-- 6. Track URL across multiple scans
SELECT scan_job_id, status_code, crawled_at 
FROM crawled_endpoints 
WHERE url_hash = $1 
ORDER BY crawled_at DESC;
```

---

## 8. Integration with Existing Architecture

### 8.1 Relationship to Existing Tables

```
assets (1) ──< (many) batch_scan_jobs (1) ──< (many) crawled_endpoints
                                                           │
                                                           │ (1:1)
                                                           ↓
                                                  endpoint_response_bodies
                                                           │
                                                           │ (1:many)
                                                           ├──< detected_technologies
                                                           └──< detected_forms
```

### 8.2 Module Profile Configuration

**Example row in `scan_module_profiles`:**

```json
{
  "name": "katana",
  "module_type": "consumer",
  "consumes_from_table": "http_probes",
  "produces_to_table": "crawled_endpoints",
  "input_filter": {
    "status_code": [200],
    "chain_status_code_ends_with": "200"
  },
  "output_columns": ["url", "status_code", "content_type", "response_headers"],
  "batch_size": 20,
  "concurrency": 2,
  "env_template": {
    "CRAWL_DEPTH": "1",
    "HEADLESS_MODE": "true",
    "CHROME_PATH": "/usr/bin/chromium-browser"
  }
}
```

---

## 9. Data Volume Projections

### 9.1 Test Results (60 seconds, 1 URL)

- **Endpoints Found:** 9
- **Total Data:** 2.8 MB
- **Average per Endpoint:** ~311 KB
- **Rate:** ~9 endpoints/minute

### 9.2 Production Estimates

| Scenario | URLs | Depth | Est. Endpoints | Est. Storage | Notes |
|----------|------|-------|----------------|--------------|-------|
| **Small Scan** | 10 URLs | 1 | ~100 | ~30 MB | Single subdomain |
| **Medium Scan** | 100 URLs | 1 | ~1,000 | ~300 MB | Multiple subdomains |
| **Large Scan** | 100 URLs | 2 | ~10,000+ | ~3 GB | Full site crawl |
| **Asset Scan** | 500 URLs | 1 | ~5,000 | ~1.5 GB | Entire asset |

**💡 Insight:** For most bug bounty recon, depth-1 crawls of 200-probed hosts will yield manageable data volumes (< 1GB per scan).

---

## 10. Recommendations

### 10.1 Immediate Actions (MVP)

1. ✅ Implement `crawled_endpoints` table with core fields
2. ✅ Implement `endpoint_response_bodies` table (separate storage)
3. ✅ Add per-scan deduplication (`scan_job_id + url_hash`)
4. ✅ Store full response bodies for depth ≤ 2 crawls
5. ✅ Add indexes for common query patterns

### 10.2 Future Enhancements

1. ⏳ Add `detected_technologies` table when Wappalyzer is enabled
2. ⏳ Add `detected_forms` table for form discovery
3. ⏳ Implement response body compression (after 7 days)
4. ⏳ Add S3 archival for old scan data (after 30 days)
5. ⏳ Track `source_url`, `discovered_from` fields (requires Go code changes)

### 10.3 Code Changes Needed

**In Katana module (Go):**
- Parse `response.headers` to extract `content-type`
- Generate `url_hash` using SHA256
- Handle NULL values for failed requests
- Batch INSERT for performance (100-500 rows per transaction)

**In API (FastAPI):**
- Add endpoints to query crawled data
- Add pagination for large result sets
- Add filters (status_code, content_type, etc.)

---

## 11. Testing Plan

### 11.1 Schema Validation Tests

```sql
-- Test 1: Insert valid endpoint
INSERT INTO crawled_endpoints (scan_job_id, url, url_hash, method, status_code, content_type, response_headers, crawled_at, depth)
VALUES (1, 'https://example.com/', 'abc123...', 'GET', 200, 'text/html', '{"server": "nginx"}'::jsonb, NOW(), 0);

-- Test 2: Verify deduplication constraint
-- Should fail with UNIQUE violation
INSERT INTO crawled_endpoints (scan_job_id, url, url_hash, method, crawled_at, depth)
VALUES (1, 'https://example.com/', 'abc123...', 'GET', NOW(), 0);

-- Test 3: Query with JSONB filter
SELECT * FROM crawled_endpoints WHERE response_headers->>'server' = 'nginx';

-- Test 4: Join with response bodies
SELECT ce.url, erb.body_size 
FROM crawled_endpoints ce
LEFT JOIN endpoint_response_bodies erb ON ce.id = erb.endpoint_id
WHERE ce.scan_job_id = 1;
```

### 11.2 Load Testing

1. Insert 10,000 endpoints and measure query performance
2. Test index effectiveness with `EXPLAIN ANALYZE`
3. Verify UNIQUE constraint performance under concurrent inserts

---

## 12. Conclusion

The Katana test results demonstrate a **clean, predictable output structure** suitable for relational database storage. The proposed schema balances:

✅ **Normalization** - Separate tables for different data types  
✅ **Performance** - Strategic indexes on query paths  
✅ **Scalability** - Deduplication and optional compression  
✅ **Flexibility** - JSONB for semi-structured data (headers)  
✅ **Future-Proofing** - Optional tables for technologies/forms  

**Next Steps:**
1. Review and approve schema design
2. Generate migration SQL files
3. Implement Go code for data insertion
4. Run longer tests (5-10 minutes) with multiple URLs to validate schema under realistic load

---

**Document Version:** 1.0  
**Last Updated:** November 20, 2025  
**Status:** ✅ Ready for Review

