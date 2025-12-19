# URL Resolver Implementation Plan

**Created**: December 19, 2025  
**Status**: ✅ Phases 1-5 Complete  
**Estimated Effort**: ~2 days (12-14 hours)

### Progress
- ✅ Phase 1: Database Schema (Completed)
- ✅ Phase 2: Create url-resolver Go container (Completed)
- ✅ Phase 3: Modify Katana to publish URLs to stream (Completed)
- ✅ Phase 4: Update orchestrator to integrate url-resolver (Completed)
- ✅ Phase 5: Frontend 'URLs' Tab (Completed)
- ⏳ Phase 6: Testing & Documentation (Pending)

---

## Executive Summary

Create a dedicated **URL Resolver** container that probes discovered URLs and stores enriched metadata in a new `urls` table. This module acts as a centralized consumer for all URL discovery sources (Katana, Waymore, GAU, etc.).

### Key Features
- ✅ Single consumer for all URL sources
- ✅ Deduplication with multi-source tracking
- ✅ TTL-based resolution (skip fresh, re-probe stale)
- ✅ HTTPx-powered probing (same SDK, proven reliable)
- ✅ Horizontal scaling via Redis Consumer Groups

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PRODUCERS (URL Discovery)                        │
├──────────────┬──────────────┬──────────────┬───────────────────────────┤
│   Katana     │   Waymore    │     GAU      │    Future Modules         │
│ (crawled_    │  (future)    │  (future)    │                           │
│  endpoints)  │              │              │                           │
└──────┬───────┴──────┬───────┴──────┬───────┴─────────┬─────────────────┘
       │              │              │                 │
       └──────────────┴──────────────┴─────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  Redis Stream       │
                    │  "urls-discovered"  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   URL Resolver      │
                    │   (Go container)    │
                    │                     │
                    │  • Consume stream   │
                    │  • Dedupe + TTL     │
                    │  • HTTP probe       │
                    │  • Store to DB      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     urls table      │
                    │    (Supabase)       │
                    └─────────────────────┘
```

---

## Phases

### Phase 1: Database Schema
**Effort**: 30 minutes

Create the `urls` table in Supabase with all required columns, indexes, and RLS policies.

#### Schema

```sql
-- New urls table for resolved URL data
CREATE TABLE urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    
    -- Core URL data
    url TEXT NOT NULL,
    url_hash TEXT NOT NULL,                  -- SHA256 hash for deduplication
    domain TEXT NOT NULL,                    -- Extracted domain for filtering
    path TEXT,                               -- Extracted path
    query_params JSONB DEFAULT '{}',         -- Parsed query string
    
    -- Discovery tracking (supports multiple sources)
    sources JSONB DEFAULT '[]',              -- ['katana', 'waymore', 'gau']
    first_discovered_by TEXT NOT NULL,       -- First source to find it
    first_discovered_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Resolution metadata (populated by URL Resolver)
    resolved_at TIMESTAMPTZ,                 -- NULL = not yet resolved
    is_alive BOOLEAN,                        -- NULL = unknown, true/false
    status_code INTEGER,
    content_type TEXT,
    content_length INTEGER,
    response_time_ms INTEGER,
    
    -- Enrichment data
    title TEXT,
    final_url TEXT,                          -- After redirects
    redirect_chain JSONB DEFAULT '[]',       -- Status codes through redirects
    webserver TEXT,                          -- Server header
    technologies JSONB DEFAULT '[]',         -- Detected tech stack
    
    -- Classification
    has_params BOOLEAN GENERATED ALWAYS AS (query_params != '{}') STORED,
    file_extension TEXT,                     -- .php, .aspx, .js, etc.
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(asset_id, url_hash)               -- No duplicate URLs per asset
);

-- Indexes for common queries
CREATE INDEX idx_urls_asset_id ON urls(asset_id);
CREATE INDEX idx_urls_domain ON urls(domain);
CREATE INDEX idx_urls_first_discovered_by ON urls(first_discovered_by);
CREATE INDEX idx_urls_is_alive ON urls(is_alive);
CREATE INDEX idx_urls_status_code ON urls(status_code);
CREATE INDEX idx_urls_has_params ON urls(has_params);
CREATE INDEX idx_urls_file_extension ON urls(file_extension);
CREATE INDEX idx_urls_resolved_at ON urls(resolved_at);

-- RLS Policy
ALTER TABLE urls ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can read all urls"
ON urls FOR SELECT
TO authenticated
USING (true);
```

#### Tasks
- [ ] Execute schema SQL in Supabase SQL Editor
- [ ] Verify table created successfully
- [ ] Verify indexes created
- [ ] Verify RLS policy active

---

### Phase 2: URL Resolver Container
**Effort**: 4-5 hours

Create the Go container that consumes URLs from Redis stream, probes them, and stores results.

#### Directory Structure

```
backend/containers/url-resolver/
├── main.go              # Entry point, mode routing
├── streaming.go         # Redis stream consumer logic
├── scanner.go           # HTTP probing using httpx SDK
├── database.go          # Supabase client operations
├── models.go            # URLRecord struct
├── dedup.go             # URL normalization + hashing
├── Dockerfile           # Container build
├── go.mod
└── go.sum
```

#### Key Components

**1. Config (Environment Variables)**
```
STREAMING_MODE=true
STREAM_INPUT_KEY=scan:{job_id}:urls-discovered
CONSUMER_GROUP=url-resolver-consumers
CONSUMER_NAME=url-resolver-{task_id}
REDIS_HOST=...
REDIS_PORT=6379
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SCAN_JOB_ID=...
ASSET_ID=...
BATCH_ID=...
RESOLUTION_TTL_HOURS=24       # URLs resolved within 24h are skipped
PROBE_BATCH_SIZE=100          # URLs to probe in parallel
```

**2. Stream Message Format (Input)**
```json
{
  "url": "https://example.com/api/v1/users",
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "katana",
  "source_id": "crawled_endpoint_uuid",
  "discovered_at": "2025-12-19T15:30:00Z"
}
```

**3. Consumer Logic (with TTL)**
```
1. Receive URL message from stream
2. Normalize URL (lowercase, sort params, remove fragments)
3. Generate URL hash (SHA256)
4. Check database for existing record:
   - Not found → INSERT new record, PROBE
   - Found + resolved_at is NULL → PROBE + UPDATE
   - Found + resolved_at within TTL → SKIP (add source if new)
   - Found + resolved_at older than TTL → RE-PROBE + UPDATE
5. If probing: use httpx SDK to probe URL
6. Update record with resolution data
7. ACK message
```

**4. Probing (using httpx SDK)**
```go
// Same SDK as HTTPx container - proven reliable
options := runner.Options{
    Methods:         "GET",
    InputTargetHost: goflags.StringSlice([]string{url}),
    TechDetect:      true,
    StatusCode:      true,
    ExtractTitle:    true,
    FollowRedirects: true,
    // ... same options as HTTPx
}
```

#### Tasks
- [ ] Create directory structure
- [ ] Implement `go.mod` with dependencies
- [ ] Implement `models.go` (URLRecord struct)
- [ ] Implement `dedup.go` (URL normalization + hashing)
- [ ] Implement `database.go` (Supabase CRUD for urls table)
- [ ] Implement `scanner.go` (httpx SDK integration)
- [ ] Implement `streaming.go` (Redis consumer with TTL logic)
- [ ] Implement `main.go` (entry point)
- [ ] Create `Dockerfile`
- [ ] Test locally with Docker

---

### Phase 3: Modify Katana (Producer)
**Effort**: 1-2 hours

Update Katana to publish discovered URLs to the `urls-discovered` stream.

#### Changes Required

**1. Add Stream Output Configuration**
```go
// internal/config/config.go
StreamOutputKey string // Redis stream for URL resolver
```

**2. Add Publishing Logic**
```go
// internal/stream/consumer.go - after storing to crawled_endpoints
if c.cfg.StreamOutputKey != "" {
    for _, endpoint := range endpoints {
        c.publishToURLStream(endpoint)
    }
}
```

**3. Implement `publishToURLStream()`**
```go
func (c *Consumer) publishToURLStream(endpoint *models.CrawledEndpoint) error {
    _, err := c.redisClient.XAdd(c.ctx, &redis.XAddArgs{
        Stream: c.cfg.StreamOutputKey,
        Values: map[string]interface{}{
            "url":           endpoint.URL,
            "asset_id":      endpoint.AssetID,
            "source":        "katana",
            "source_id":     endpoint.ID,
            "discovered_at": time.Now().UTC().Format(time.RFC3339),
        },
    }).Result()
    return err
}
```

**4. Send Completion Marker**
```go
// After crawl loop completes
if c.cfg.StreamOutputKey != "" {
    c.sendURLStreamCompletionMarker(totalURLsPublished)
}
```

#### Tasks
- [ ] Add `StreamOutputKey` to Katana config
- [ ] Implement `publishToURLStream()` function
- [ ] Implement `sendURLStreamCompletionMarker()` function
- [ ] Update consumer loop to publish after storing
- [ ] Rebuild Katana container
- [ ] Push to ECR

---

### Phase 4: Orchestrator Integration
**Effort**: 1-2 hours

Update the pipeline orchestrator to launch URL Resolver after Katana.

#### Changes Required

**1. Update `scan_pipeline.py`**
```python
# Add URL Resolver stage after Katana
MODULE_TIMEOUTS = {
    # ... existing
    "url-resolver": 1800,  # 30 min timeout
}

# Generate stream key for Katana → URL Resolver
katana_output_stream = f"scan:{scan_job_id}:urls-discovered"

# Launch URL Resolver as consumer of Katana's output
for i in range(scale_factor):
    await orchestrator.launch_streaming_consumer(
        module="url-resolver",
        stream_input_key=katana_output_stream,
        consumer_group="url-resolver-consumers",
        consumer_name=f"url-resolver-{i}",
        # ... other params
    )
```

**2. Update `batch_workflow_orchestrator.py`**
- Add URL Resolver task definition reference
- Add environment variable mappings

**3. Add Terraform Resources**
- ECR repository for url-resolver
- ECS task definition

#### Tasks
- [ ] Update `scan_pipeline.py` with URL Resolver stage
- [ ] Update `batch_workflow_orchestrator.py` with URL Resolver support
- [ ] Add `url-resolver` to `ReconModule` enum in `schemas/recon.py`
- [ ] Update `valid_modules` constraint in database (add 'url-resolver')
- [ ] Add Terraform for ECR repository
- [ ] Add Terraform for ECS task definition
- [ ] Deploy infrastructure
- [ ] Push URL Resolver container to ECR

---

### Phase 5: Backend API
**Effort**: 2 hours

Create API endpoints for the `urls` table.

#### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/urls` | List URLs with filters |
| GET | `/api/v1/urls/{id}` | Get single URL details |
| GET | `/api/v1/urls/stats` | Get URL statistics |

#### Filters
- `asset_id` - Filter by asset
- `is_alive` - Filter by alive status
- `status_code` - Filter by status code
- `has_params` - Filter URLs with query params
- `source` - Filter by discovery source
- `domain` - Filter by domain

#### Tasks
- [ ] Create `backend/app/api/v1/urls.py`
- [ ] Add Pydantic schemas in `schemas/urls.py`
- [ ] Register router in `api/v1/__init__.py`
- [ ] Test endpoints

---

### Phase 6: Frontend URLs Tab
**Effort**: 3-4 hours

Create a dedicated "URLs" tab in the frontend for viewing resolved URLs.

#### Components

```
frontend/src/
├── app/
│   └── urls/
│       └── page.tsx           # URLs listing page
├── components/
│   └── urls/
│       ├── URLsTable.tsx      # Data table
│       ├── URLsFilters.tsx    # Filter controls
│       └── URLDetails.tsx     # Detail modal/panel
```

#### Features
- Table with sortable columns
- Filters: status code, alive, has params, source, domain
- Search by URL
- Export to CSV
- Stats summary (total, alive, with params, by source)

#### Tasks
- [ ] Create URLs page layout
- [ ] Implement URLsTable component
- [ ] Implement filters
- [ ] Add to navigation
- [ ] Style with existing design system

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| HTTPx SDK URL handling differs from subdomain | Low | Medium | Test early in Phase 2 |
| High URL volume overwhelms resolver | Medium | Medium | Horizontal scaling with Consumer Groups |
| Duplicate probing wastes resources | Low | Low | TTL + deduplication logic |

---

## Success Criteria

- [ ] URLs from Katana appear in `urls` table
- [ ] URL Resolver correctly probes and enriches URLs
- [ ] TTL prevents re-probing fresh URLs
- [ ] Multiple sources correctly tracked per URL
- [ ] Frontend displays URLs with filters
- [ ] Horizontal scaling works (multiple resolver tasks)

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Streaming pipeline | ✅ Complete | Subfinder → DNSx/HTTPx → Katana |
| Redis Consumer Groups | ✅ Complete | Horizontal scaling implemented |
| Katana producing to stream | 🔄 Needs update | Phase 3 |
| url-resolver in ECS | ❌ Not started | Phase 4 |

---

## Changelog

| Date | Change |
|------|--------|
| 2025-12-19 | Initial plan created |


