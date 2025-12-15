# Katana Module Implementation Plan
**Project:** Web Crawler Module Integration into NeoBot-Net v2  
**Module Name:** `katana-go`  
**Status:** Planning Phase  
**Created:** November 21, 2025  
**Last Updated:** November 21, 2025

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [Dependencies](#dependencies)
3. [Implementation Phases](#implementation-phases)
4. [Database Schema](#database-schema)
5. [Module Configuration](#module-configuration)
6. [Container Implementation](#container-implementation)
7. [Testing Strategy](#testing-strategy)
8. [Deployment Checklist](#deployment-checklist)
9. [Progress Tracker](#progress-tracker)

---

## Overview

### Purpose
Integrate ProjectDiscovery's Katana web crawler as a consumer module in the NeoBot-Net v2 scan engine to automatically discover endpoints, paths, and URLs from HTTP probes.

### Module Characteristics
- **Type:** Consumer Module (depends on HTTPx)
- **Execution Mode:** Batch + Streaming (Redis Streams)
- **Input Source:** `http_probes` table (status_code = 200 OR chain_status_codes ends with 200)
- **Output Target:** `crawled_endpoints` table
- **Estimated Duration:** 300 seconds (5 minutes) per batch of 20 URLs

### Key Features
- ✅ Headless crawling (JavaScript rendering enabled by default)
- ✅ Depth: 1 level (configurable via module profile)
- ✅ Scope control using apex domains from asset
- ✅ Global deduplication per asset (in-memory + database)
- ✅ Source URL tracking for attack surface mapping
- ✅ Extension filtering (no images, CSS, fonts, etc.)
- ✅ Metadata-only storage (no response bodies)
- ✅ Seed URL flagging for UI filtering

---

## Dependencies

### Module Dependencies
```
subfinder-go → dnsx-go → httpx-go → katana-go
```

**Upstream Modules:**
- `httpx-go` - Provides HTTP probe results as input

**Dependency Justification:**
Katana requires live URLs (200 OK status) to crawl. These come from HTTPx probes of subdomains discovered by Subfinder and resolved by DNSx.

### System Requirements
- **Go:** 1.21+
- **Chromium:** Latest (for headless mode)
- **Non-root user:** Required for headless crawling
- **Resource Allocation:**
  - Small batch (1-10 URLs): 1 vCPU, 1 GB RAM
  - Medium batch (11-50 URLs): 2 vCPU, 2 GB RAM
  - Large batch (51-100 URLs): 4 vCPU, 4 GB RAM

---

## Implementation Phases

### Phase 1: Database Schema Implementation ⏳
**Status:** Not Started  
**Duration:** 1-2 hours  
**Owner:** TBD

#### Tasks:
- [ ] 1.1. Create `crawled_endpoints` table in `schema.sql`
- [ ] 1.2. Add table indexes for performance
- [ ] 1.3. Add table comments and column documentation
- [ ] 1.4. Create migration script for existing databases
- [ ] 1.5. Test schema on local Supabase instance
- [ ] 1.6. Verify foreign key constraints work correctly

**Deliverables:**
- Updated `schema.sql` with new table
- Migration script: `migrations/20251121_add_crawled_endpoints.sql`

---

### Phase 2: Module Profile Configuration ⏳
**Status:** Not Started  
**Duration:** 30 minutes  
**Owner:** TBD

#### Tasks:
- [ ] 2.1. Define module profile JSON configuration
- [ ] 2.2. Configure resource scaling rules
- [ ] 2.3. Set batch size and duration estimates
- [ ] 2.4. Define environment variable contract
- [ ] 2.5. Insert module profile into `scan_module_profiles` table
- [ ] 2.6. Validate profile against schema constraints

**Deliverables:**
- Module profile SQL insert script: `config/katana_module_profile.sql`
- Environment variable documentation

---

### Phase 3: Container Implementation ⏳
**Status:** Not Started  
**Duration:** 4-6 hours  
**Owner:** TBD

#### Sub-phases:

##### 3.1. Project Setup
- [ ] Create `/backend/containers/katana-go/` directory
- [ ] Initialize Go module: `go mod init katana-go`
- [ ] Copy Dockerfile template from test container
- [ ] Setup project structure:
  ```
  katana-go/
  ├── main.go
  ├── go.mod
  ├── go.sum
  ├── Dockerfile
  ├── README.md
  ├── internal/
  │   ├── config/
  │   │   └── config.go       # Environment variable parsing
  │   ├── database/
  │   │   ├── db.go           # Supabase client
  │   │   └── repository.go   # CRUD operations
  │   ├── dedup/
  │   │   └── dedup.go        # In-memory deduplication
  │   ├── scanner/
  │   │   ├── scanner.go      # Katana wrapper
  │   │   └── result.go       # Result processing
  │   └── stream/
  │       ├── producer.go     # Redis Streams producer
  │       └── consumer.go     # Redis Streams consumer
  └── pkg/
      └── models/
          └── endpoint.go     # Data models
  ```

##### 3.2. Core Implementation
- [ ] Implement configuration parser (`internal/config/`)
- [ ] Implement database client (`internal/database/`)
- [ ] Implement deduplication logic (`internal/dedup/`)
- [ ] Implement Katana scanner wrapper (`internal/scanner/`)
- [ ] Implement Redis Streams producer/consumer (`internal/stream/`)
- [ ] Implement graceful shutdown handler
- [ ] Add logging with structured output

##### 3.3. Execution Modes
- [ ] **Simple Mode:** Single URL input via `TARGET_URL`
- [ ] **Batch Mode:** Multiple URLs from `TARGET_URLS` (comma-separated)
- [ ] **Streaming Mode:** Redis Streams consumer reading from `scan:httpx:results`

##### 3.4. Data Pipeline
- [ ] Fetch HTTP probes from database (WHERE status_code = 200)
- [ ] Extract apex domains for scope control
- [ ] Configure Katana with proper options
- [ ] Capture results with source URL tracking
- [ ] Deduplicate in-memory (URL normalization + hashing)
- [ ] Batch insert to `crawled_endpoints` table
- [ ] Publish results to Redis Stream: `scan:katana:results`

**Deliverables:**
- Production-ready Go application
- Multi-stage Dockerfile
- README with usage instructions

---

### Phase 4: Database Integration ⏳
**Status:** Not Started  
**Duration:** 2-3 hours  
**Owner:** TBD

#### Tasks:
- [ ] 4.1. Implement Supabase client with connection pooling
- [ ] 4.2. Create repository functions:
  - [ ] `FetchHTTPProbes(assetID, scanJobID)` - Get seed URLs
  - [ ] `FetchApexDomains(assetID)` - Get scope for crawling
  - [ ] `UpsertEndpoints(endpoints)` - Batch insert with conflict handling
  - [ ] `GetExistingEndpoints(assetID, hashes)` - Check for existing URLs
- [ ] 4.3. Implement ON CONFLICT logic for deduplication:
  ```sql
  ON CONFLICT (asset_id, url_hash) DO UPDATE SET
    last_seen_at = EXCLUDED.last_seen_at,
    times_discovered = crawled_endpoints.times_discovered + 1,
    status_code = COALESCE(EXCLUDED.status_code, crawled_endpoints.status_code)
  ```
- [ ] 4.4. Add database error handling and retries
- [ ] 4.5. Implement connection health checks

**Deliverables:**
- Database repository with CRUD operations
- Unit tests for repository functions

---

### Phase 5: Redis Streams Integration ⏳
**Status:** Not Started  
**Duration:** 2-3 hours  
**Owner:** TBD

#### Tasks:
- [ ] 5.1. Implement Redis Streams consumer:
  - [ ] Read from `scan:httpx:results` stream
  - [ ] Parse HTTP probe messages
  - [ ] Filter for 200 OK status codes
  - [ ] Batch URLs for efficient crawling
- [ ] 5.2. Implement Redis Streams producer:
  - [ ] Publish to `scan:katana:results` stream
  - [ ] Message format: `{"url": "...", "status_code": 200, "source_url": "...", ...}`
  - [ ] Include metadata for downstream modules
- [ ] 5.3. Handle consumer group logic:
  - [ ] Consumer group: `katana-workers`
  - [ ] Consumer name: `katana-{HOSTNAME}`
  - [ ] Auto-claim pending messages
- [ ] 5.4. Implement acknowledgment (XACK) after successful processing

**Deliverables:**
- Redis Streams consumer/producer implementation
- Integration tests with local Redis

---

### Phase 6: Testing & Validation ⏳
**Status:** Not Started  
**Duration:** 3-4 hours  
**Owner:** TBD

#### Test Levels:

##### 6.1. Unit Tests
- [ ] Configuration parsing tests
- [ ] URL normalization tests
- [ ] Deduplication logic tests
- [ ] Database repository mocks

##### 6.2. Integration Tests
- [ ] Supabase connection tests
- [ ] Redis Streams pub/sub tests
- [ ] Katana execution tests with mock data

##### 6.3. End-to-End Tests
- [ ] **Simple Mode Test:**
  ```bash
  docker run --rm \
    -e EXECUTION_MODE=simple \
    -e TARGET_URL=https://example.com \
    -e SUPABASE_URL=... \
    -e SUPABASE_KEY=... \
    katana-go:latest
  ```
- [ ] **Batch Mode Test:**
  ```bash
  docker run --rm \
    -e EXECUTION_MODE=batch \
    -e TARGET_URLS=https://site1.com,https://site2.com \
    -e ASSET_ID=<uuid> \
    -e SCAN_JOB_ID=<uuid> \
    katana-go:latest
  ```
- [ ] **Streaming Mode Test:**
  ```bash
  docker run --rm \
    -e EXECUTION_MODE=streaming \
    -e REDIS_HOST=redis.local \
    -e CONSUMER_GROUP=katana-workers \
    katana-go:latest
  ```

##### 6.4. Performance Tests
- [ ] Test with 100 URLs (expected duration: ~10 minutes)
- [ ] Monitor memory usage during crawl
- [ ] Validate deduplication efficiency
- [ ] Measure database insert throughput

**Deliverables:**
- Test suite with 80%+ coverage
- Performance benchmarks document

---

### Phase 7: Backend API Integration ⏳
**Status:** Not Started  
**Duration:** 2-3 hours  
**Owner:** TBD

#### Tasks:
- [ ] 7.1. Add Katana module to backend execution pipeline
- [ ] 7.2. Implement API endpoint: `POST /api/v1/scan/{assetId}/katana`
- [ ] 7.3. Update scan orchestration logic:
  - [ ] Ensure HTTPx completes before Katana starts
  - [ ] Trigger Katana after HTTPx publishes to Redis
- [ ] 7.4. Add module status tracking
- [ ] 7.5. Implement error handling and retry logic

**Deliverables:**
- Backend API changes
- Postman collection for testing

---

### Phase 8: Frontend Dashboard Integration ⏳
**Status:** Not Started  
**Duration:** 4-6 hours  
**Owner:** TBD

#### Tasks:
- [ ] 8.1. Create `CrawledEndpoints` component
- [ ] 8.2. Add API client methods:
  - [ ] `GET /api/v1/assets/{assetId}/endpoints` - List endpoints
  - [ ] `GET /api/v1/assets/{assetId}/endpoints/{endpointId}` - Endpoint details
- [ ] 8.3. Design endpoint table with columns:
  - [ ] URL, Method, Status Code, Content Type, Source URL, Discovered Count, First/Last Seen
- [ ] 8.4. Add filtering options:
  - [ ] Filter by status code (200, 404, 301, etc.)
  - [ ] Toggle "Hide seed URLs"
  - [ ] Search by URL
- [ ] 8.5. Add export functionality (CSV, JSON)
- [ ] 8.6. Add endpoint discovery chart (timeline view)

**Deliverables:**
- Next.js pages/components for endpoint viewing
- Shadcn UI components for data tables

---

### Phase 9: Documentation ⏳
**Status:** Not Started  
**Duration:** 2-3 hours  
**Owner:** TBD

#### Tasks:
- [ ] 9.1. Update main README with Katana module
- [ ] 9.2. Create module-specific README: `backend/containers/katana-go/README.md`
- [ ] 9.3. Document environment variables
- [ ] 9.4. Create troubleshooting guide
- [ ] 9.5. Update architecture diagrams
- [ ] 9.6. Create user guide for dashboard

**Deliverables:**
- Comprehensive documentation
- Updated architecture diagrams

---

### Phase 10: Deployment ⏳
**Status:** Not Started  
**Duration:** 2-3 hours  
**Owner:** TBD

#### Tasks:
- [ ] 10.1. Build and push Docker image to ECR
- [ ] 10.2. Create ECS task definition
- [ ] 10.3. Deploy to staging environment
- [ ] 10.4. Run end-to-end tests in staging
- [ ] 10.5. Monitor logs and metrics
- [ ] 10.6. Deploy to production
- [ ] 10.7. Insert module profile into production database

**Deliverables:**
- Deployed Katana module in production
- Monitoring dashboard

---

## Database Schema

### Table: `crawled_endpoints`

```sql
-- ============================================================
-- Table: crawled_endpoints
-- Purpose: Store web endpoints discovered by Katana crawler
-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."crawled_endpoints" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL PRIMARY KEY,
    "asset_id" "uuid" NOT NULL,
    "scan_job_id" "uuid",
    "url" "text" NOT NULL,
    "url_hash" "text" NOT NULL,
    "method" "text" DEFAULT 'GET' NOT NULL,
    "source_url" "text",
    "is_seed_url" boolean DEFAULT false NOT NULL,
    "status_code" integer,
    "content_type" "text",
    "content_length" bigint,
    "first_seen_at" timestamp with time zone NOT NULL,
    "last_seen_at" timestamp with time zone NOT NULL,
    "times_discovered" integer DEFAULT 1 NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    
    -- Constraints
    CONSTRAINT "crawled_endpoints_method_check" CHECK (("method" = ANY (ARRAY['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']))),
    CONSTRAINT "crawled_endpoints_times_discovered_check" CHECK (("times_discovered" >= 1)),
    CONSTRAINT "crawled_endpoints_asset_url_unique" UNIQUE ("asset_id", "url_hash"),
    
    -- Foreign Keys
    CONSTRAINT "crawled_endpoints_asset_id_fkey" FOREIGN KEY ("asset_id") REFERENCES "public"."assets"("id") ON DELETE CASCADE,
    CONSTRAINT "crawled_endpoints_scan_job_id_fkey" FOREIGN KEY ("scan_job_id") REFERENCES "public"."batch_scan_jobs"("id") ON DELETE SET NULL
);

-- Indexes for performance
CREATE INDEX "idx_crawled_endpoints_asset_id" ON "public"."crawled_endpoints" USING btree ("asset_id");
CREATE INDEX "idx_crawled_endpoints_scan_job_id" ON "public"."crawled_endpoints" USING btree ("scan_job_id");
CREATE INDEX "idx_crawled_endpoints_status_code" ON "public"."crawled_endpoints" USING btree ("status_code");
CREATE INDEX "idx_crawled_endpoints_is_seed_url" ON "public"."crawled_endpoints" USING btree ("is_seed_url");
CREATE INDEX "idx_crawled_endpoints_url_hash" ON "public"."crawled_endpoints" USING btree ("url_hash");
CREATE INDEX "idx_crawled_endpoints_first_seen" ON "public"."crawled_endpoints" USING btree ("first_seen_at" DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE "public"."crawled_endpoints" ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see endpoints for their assets
CREATE POLICY "Users can view their own crawled endpoints"
ON "public"."crawled_endpoints"
FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM "public"."assets"
        WHERE "assets"."id" = "crawled_endpoints"."asset_id"
        AND "assets"."user_id" = "auth"."uid"()
    )
);

-- Table and column comments
COMMENT ON TABLE "public"."crawled_endpoints" IS 'Stores web endpoints discovered by Katana crawler. Includes URL metadata, status codes, source tracking, and deduplication fields.';
COMMENT ON COLUMN "public"."crawled_endpoints"."url" IS 'Full URL of the discovered endpoint (normalized for deduplication)';
COMMENT ON COLUMN "public"."crawled_endpoints"."url_hash" IS 'SHA256 hash of normalized URL for fast lookups and deduplication';
COMMENT ON COLUMN "public"."crawled_endpoints"."source_url" IS 'The URL from which this endpoint was discovered. Use for attack surface mapping and site structure analysis.';
COMMENT ON COLUMN "public"."crawled_endpoints"."is_seed_url" IS 'True if this URL was used as an initial seed for crawling (from http_probes). Use for UI filtering.';
COMMENT ON COLUMN "public"."crawled_endpoints"."times_discovered" IS 'Number of times this URL was discovered across crawls. Higher values indicate hub pages or frequently linked resources.';
COMMENT ON COLUMN "public"."crawled_endpoints"."first_seen_at" IS 'Timestamp when this URL was first discovered';
COMMENT ON COLUMN "public"."crawled_endpoints"."last_seen_at" IS 'Timestamp when this URL was most recently rediscovered';

-- Set table owner
ALTER TABLE "public"."crawled_endpoints" OWNER TO "postgres";
```

### Migration Script

Create file: `migrations/20251121_add_crawled_endpoints.sql`

```sql
-- Migration: Add crawled_endpoints table for Katana module
-- Date: 2025-11-21
-- Author: NeoBot-Net v2 Team

BEGIN;

-- Create table (use full schema above)
-- ... (full CREATE TABLE statement)

-- Verify foreign keys exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'assets') THEN
        RAISE EXCEPTION 'Required table "assets" does not exist';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'batch_scan_jobs') THEN
        RAISE EXCEPTION 'Required table "batch_scan_jobs" does not exist';
    END IF;
END $$;

COMMIT;
```

---

## Module Configuration

### Module Profile

Insert into `scan_module_profiles` table:

```sql
INSERT INTO "public"."scan_module_profiles" (
    "module_name",
    "version",
    "supports_batching",
    "max_batch_size",
    "resource_scaling",
    "estimated_duration_per_domain",
    "task_definition_template",
    "container_name",
    "is_active",
    "optimization_hints",
    "dependencies"
)
VALUES (
    'katana-go',
    '1.0.0',
    true,
    20,  -- Process up to 20 URLs per batch
    '{
        "rules": [
            {
                "threshold": 10,
                "cpu": "1024",
                "memory": "1024",
                "description": "Small batch (1-10 URLs)"
            },
            {
                "threshold": 50,
                "cpu": "2048",
                "memory": "2048",
                "description": "Medium batch (11-50 URLs)"
            },
            {
                "threshold": 100,
                "cpu": "4096",
                "memory": "4096",
                "description": "Large batch (51-100 URLs)"
            }
        ]
    }'::jsonb,
    300,  -- 5 minutes per batch of 20 URLs
    'arn:aws:ecs:us-east-1:ACCOUNT_ID:task-definition/katana-go',
    'katana-go',
    true,
    '{
        "crawl_depth": 1,
        "headless_mode": true,
        "javascript_parsing": true,
        "rate_limit": 150,
        "concurrency": 10,
        "parallelism": 10,
        "timeout": 10,
        "strategy": "depth-first",
        "scope_control": "apex_domains"
    }'::jsonb,
    ARRAY['httpx-go']  -- Depends on HTTPx completing first
);
```

### Environment Variable Contract

The module expects these environment variables:

#### Required Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `EXECUTION_MODE` | String | Execution mode: `simple`, `batch`, or `streaming` | `batch` |
| `SUPABASE_URL` | String | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_KEY` | String | Supabase service role key | `eyJ...` |

#### Mode-Specific Variables

**Simple Mode:**
| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `TARGET_URL` | String | Single URL to crawl | `https://example.com` |
| `ASSET_ID` | UUID | Asset ID for scope control | `123e4567-e89b-12d3...` |

**Batch Mode:**
| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `TARGET_URLS` | String | Comma-separated URLs | `https://site1.com,https://site2.com` |
| `ASSET_ID` | UUID | Asset ID for scope control | `123e4567-e89b-12d3...` |
| `SCAN_JOB_ID` | UUID | Batch scan job ID | `123e4567-e89b-12d3...` |

**Streaming Mode:**
| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `REDIS_HOST` | String | Redis server host | `redis.internal` |
| `REDIS_PORT` | Integer | Redis server port | `6379` |
| `REDIS_PASSWORD` | String | Redis password (optional) | `secret123` |
| `CONSUMER_GROUP` | String | Redis consumer group | `katana-workers` |
| `INPUT_STREAM` | String | Input stream name | `scan:httpx:results` |
| `OUTPUT_STREAM` | String | Output stream name | `scan:katana:results` |

#### Optional Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CRAWL_DEPTH` | Integer | `1` | Maximum crawl depth |
| `HEADLESS_MODE` | Boolean | `true` | Enable headless Chrome |
| `RATE_LIMIT` | Integer | `150` | Max requests per second |
| `CONCURRENCY` | Integer | `10` | Concurrent crawling goroutines |
| `PARALLELISM` | Integer | `10` | Parallel URL processing |
| `TIMEOUT` | Integer | `10` | Request timeout in seconds |
| `STRATEGY` | String | `depth-first` | Crawl strategy: `depth-first` or `breadth-first` |
| `LOG_LEVEL` | String | `info` | Logging level: `debug`, `info`, `warn`, `error` |

---

## Container Implementation

### Directory Structure

```
backend/containers/katana-go/
├── main.go                      # Entry point
├── go.mod                       # Go module definition
├── go.sum                       # Go module checksums
├── Dockerfile                   # Multi-stage build
├── README.md                    # Usage documentation
├── .dockerignore               # Docker ignore rules
├── internal/
│   ├── config/
│   │   └── config.go           # Environment config parsing
│   ├── database/
│   │   ├── db.go               # Supabase client
│   │   └── repository.go       # CRUD operations
│   ├── dedup/
│   │   ├── dedup.go            # URL normalization & dedup
│   │   └── hasher.go           # SHA256 hashing
│   ├── scanner/
│   │   ├── scanner.go          # Katana wrapper
│   │   ├── options.go          # Katana options builder
│   │   └── result.go           # Result processing
│   └── stream/
│       ├── producer.go         # Redis Streams producer
│       └── consumer.go         # Redis Streams consumer
└── pkg/
    └── models/
        ├── endpoint.go         # Endpoint model
        └── probe.go            # HTTP probe model
```

### Key Implementation Details

#### 1. URL Normalization (`internal/dedup/dedup.go`)
```go
func NormalizeURL(rawURL string) (string, error) {
    parsed, err := url.Parse(rawURL)
    if err != nil {
        return "", err
    }
    
    // Lowercase scheme and host
    parsed.Scheme = strings.ToLower(parsed.Scheme)
    parsed.Host = strings.ToLower(parsed.Host)
    
    // Remove fragment
    parsed.Fragment = ""
    
    // Sort query parameters
    query := parsed.Query()
    parsed.RawQuery = query.Encode()
    
    // Remove trailing slash (except for root)
    path := parsed.Path
    if len(path) > 1 && strings.HasSuffix(path, "/") {
        parsed.Path = strings.TrimSuffix(path, "/")
    }
    
    return parsed.String(), nil
}

func HashURL(normalizedURL string) string {
    hash := sha256.Sum256([]byte(normalizedURL))
    return hex.EncodeToString(hash[:])
}
```

#### 2. Database Upsert (`internal/database/repository.go`)
```go
func (r *Repository) UpsertEndpoints(ctx context.Context, endpoints []models.Endpoint) error {
    query := `
        INSERT INTO crawled_endpoints (
            asset_id, scan_job_id, url, url_hash, method,
            source_url, is_seed_url, status_code, content_type,
            content_length, first_seen_at, last_seen_at, times_discovered
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $11, 1
        )
        ON CONFLICT (asset_id, url_hash) DO UPDATE SET
            last_seen_at = EXCLUDED.last_seen_at,
            times_discovered = crawled_endpoints.times_discovered + 1,
            status_code = COALESCE(EXCLUDED.status_code, crawled_endpoints.status_code),
            content_type = COALESCE(EXCLUDED.content_type, crawled_endpoints.content_type),
            content_length = COALESCE(EXCLUDED.content_length, crawled_endpoints.content_length)
        RETURNING id
    `
    
    // Batch insert logic...
}
```

#### 3. Katana Wrapper (`internal/scanner/scanner.go`)
```go
func (s *Scanner) Crawl(ctx context.Context, seedURLs []string, apexDomains []string) ([]models.Endpoint, error) {
    options := &types.Options{
        MaxDepth:      s.config.CrawlDepth,
        Headless:      s.config.HeadlessMode,
        FieldScope:    "rdn",
        Timeout:       s.config.Timeout,
        Concurrency:   s.config.Concurrency,
        Parallelism:   s.config.Parallelism,
        RateLimit:     s.config.RateLimit,
        Strategy:      s.config.Strategy,
        Scope:         apexDomains,  // Scope control
        ExtensionFilter: []string{   // Extension filtering
            "css", "jpg", "jpeg", "png", "svg", "gif",
            "mp4", "webm", "mp3", "woff", "woff2", "ttf",
        },
        OnResult: func(result output.Result) {
            s.mu.Lock()
            s.results = append(s.results, result)
            s.mu.Unlock()
        },
    }
    
    // Initialize and run crawler...
}
```

---

## Testing Strategy

### Test Coverage Goals
- **Unit Tests:** 80%+ coverage
- **Integration Tests:** All critical paths
- **E2E Tests:** All execution modes

### Test Environment Setup

```bash
# 1. Start local test stack
docker-compose -f docker-compose.test.yml up -d

# 2. Run unit tests
cd backend/containers/katana-go
go test ./... -v -cover

# 3. Run integration tests
go test ./... -tags=integration -v

# 4. Run E2E tests
./scripts/test-e2e.sh
```

### Critical Test Cases

1. **URL Normalization:**
   - Test case sensitivity (HTTP vs http)
   - Test query parameter sorting
   - Test fragment removal
   - Test trailing slash handling

2. **Deduplication:**
   - Same URL discovered twice → times_discovered increments
   - Different status codes → latest wins
   - Seed URL rediscovery → times_discovered = 2

3. **Scope Control:**
   - In-scope URL → stored
   - Out-of-scope URL → ignored
   - Subdomain of apex → stored
   - Different TLD → ignored

4. **Database Operations:**
   - Batch insert performance (100+ URLs)
   - ON CONFLICT behavior
   - Foreign key constraints
   - Transaction rollback on error

5. **Redis Streams:**
   - Message publish/subscribe
   - Consumer group coordination
   - Acknowledgment handling
   - Pending message recovery

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing (unit, integration, E2E)
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Database migration tested
- [ ] Module profile configured
- [ ] Environment variables documented

### Deployment Steps
1. [ ] Build Docker image: `docker build -t katana-go:v1.0.0 .`
2. [ ] Tag for ECR: `docker tag katana-go:v1.0.0 ECR_URL/katana-go:v1.0.0`
3. [ ] Push to ECR: `docker push ECR_URL/katana-go:v1.0.0`
4. [ ] Create ECS task definition
5. [ ] Deploy to staging environment
6. [ ] Run smoke tests in staging
7. [ ] Monitor logs for 24 hours
8. [ ] Deploy to production
9. [ ] Insert module profile into production DB
10. [ ] Monitor production metrics

### Post-Deployment
- [ ] Verify first scan completes successfully
- [ ] Check database for new endpoints
- [ ] Monitor resource usage (CPU, memory)
- [ ] Review logs for errors
- [ ] Test dashboard endpoint view
- [ ] Update team documentation

---

## Progress Tracker

### Overall Progress: 0% Complete

| Phase | Status | Progress | ETA |
|-------|--------|----------|-----|
| 1. Database Schema | ⏳ Not Started | 0% | TBD |
| 2. Module Profile | ⏳ Not Started | 0% | TBD |
| 3. Container Implementation | ⏳ Not Started | 0% | TBD |
| 4. Database Integration | ⏳ Not Started | 0% | TBD |
| 5. Redis Streams | ⏳ Not Started | 0% | TBD |
| 6. Testing | ⏳ Not Started | 0% | TBD |
| 7. Backend API | ⏳ Not Started | 0% | TBD |
| 8. Frontend Dashboard | ⏳ Not Started | 0% | TBD |
| 9. Documentation | ⏳ Not Started | 0% | TBD |
| 10. Deployment | ⏳ Not Started | 0% | TBD |

### Status Legend
- ⏳ Not Started
- 🚧 In Progress
- ✅ Complete
- ⚠️ Blocked
- ❌ Failed

### Estimated Total Duration
- **Development:** 20-30 hours
- **Testing:** 5-10 hours
- **Deployment:** 3-5 hours
- **Total:** 28-45 hours (~1 week with focused effort)

---

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Headless mode resource exhaustion | High | Medium | Implement strict resource limits per task |
| Scope leakage (crawling out-of-scope) | High | Low | Test apex domain filtering thoroughly |
| Database deadlocks on upsert | Medium | Medium | Use batch inserts with proper locking |
| Redis Streams message loss | Medium | Low | Implement consumer group with acknowledgment |
| Crawl timeouts on slow sites | Low | High | Set reasonable timeout + graceful handling |

---

## Success Criteria

### Phase 1 Complete When:
✅ Database schema deployed to staging  
✅ Can manually insert and query endpoints  
✅ RLS policies tested with test user

### Phase 3 Complete When:
✅ Container runs in all 3 execution modes  
✅ Successfully crawls test URLs  
✅ Stores results in database  
✅ No memory leaks after 10-minute run

### Production Ready When:
✅ All phases marked complete  
✅ 80%+ test coverage  
✅ Successfully processed 100+ URLs in staging  
✅ Dashboard displays endpoints correctly  
✅ Documentation reviewed and approved

---

## Next Steps

**Immediate Actions:**
1. Review and approve this implementation plan
2. Assign ownership for each phase
3. Set milestone dates
4. Begin Phase 1: Database Schema Implementation

**Questions to Resolve:**
- [ ] Should we support POST form crawling in v1.0, or defer to v1.1?
- [ ] Should we store form data (fields, values) in a separate table?
- [ ] Do we want to capture technologies/frameworks like HTTPx does?
- [ ] Should we implement a "replay" feature to re-crawl specific endpoints?

---

**Plan created:** November 21, 2025  
**Ready for review:** ✅  
**Approved by:** [ ]  
**Implementation start date:** [ ]
