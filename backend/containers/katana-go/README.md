# Katana Web Crawler Module

Production-ready web crawler module for NeoBot-Net v2 reconnaissance framework.

## Overview

Katana is a consumer module that crawls web applications discovered by the HTTPx module to find hidden endpoints, forms, and API paths. It uses headless Chrome for JavaScript rendering and depth-first crawling.

## Features

- ✅ **Headless Crawling**: JavaScript rendering via Chrome headless
- ✅ **Scope Control**: Restricts crawling to asset apex domains
- ✅ **Deduplication**: Global URL deduplication per asset (in-memory + database)
- ✅ **Source Tracking**: Tracks which page linked to each endpoint
- ✅ **Seed URL Flagging**: Distinguishes initial crawl targets from discovered links
- ✅ **Three Execution Modes**: Simple, Batch, Streaming
- ✅ **Structured Logging**: Debug, Info, Warn, Error levels with context
- ✅ **Graceful Shutdown**: SIGTERM handling with cleanup

## Dependencies

**Upstream Modules:**
- `httpx-go` - Provides HTTP probes (200 OK status) as seed URLs

**Execution Order:**
```
subfinder → dnsx → httpx → katana
```

## Architecture

```
katana-go/
├── main.go                      # Entry point, mode routing
├── internal/
│   ├── config/
│   │   ├── config.go           # Environment variable parsing
│   │   └── logger.go           # Structured logging
│   ├── database/
│   │   ├── client.go           # Supabase HTTP client
│   │   └── repository.go       # CRUD operations
│   ├── dedup/
│   │   └── dedup.go            # URL normalization + SHA256 hashing
│   ├── scanner/
│   │   ├── scanner.go          # Katana wrapper
│   │   └── options.go          # Katana configuration
│   └── models/
│       └── endpoint.go         # Data structures
└── Dockerfile                   # Multi-stage build
```

## Execution Modes

### 1. Simple Mode (Testing)

For local development and single-URL testing.

```bash
docker run --rm \
  -e EXECUTION_MODE=simple \
  -e TARGET_URLS='["https://example.com"]' \
  -e ASSET_ID=<uuid> \
  -e SCAN_JOB_ID=<uuid> \
  -e SUPABASE_URL=https://xxx.supabase.co \
  -e SUPABASE_SERVICE_ROLE_KEY=xxx \
  katana-go:latest
```

### 2. Batch Mode (Production)

For batch processing of HTTP probes from database.

```bash
docker run --rm \
  -e BATCH_MODE=true \
  -e BATCH_ID=<uuid> \
  -e ASSET_ID=<uuid> \
  -e SCAN_JOB_ID=<uuid> \
  -e BATCH_OFFSET=0 \
  -e BATCH_LIMIT=20 \
  -e SUPABASE_URL=https://xxx.supabase.co \
  -e SUPABASE_SERVICE_ROLE_KEY=xxx \
  katana-go:latest
```

### 3. Streaming Mode (Real-Time)

For consuming HTTP probes from Redis Streams.

```bash
docker run --rm \
  -e STREAMING_MODE=true \
  -e REDIS_HOST=redis.internal \
  -e REDIS_PORT=6379 \
  -e STREAM_INPUT_KEY=scan:httpx:results \
  -e CONSUMER_GROUP=katana-workers \
  -e CONSUMER_NAME=katana-task-1 \
  -e ASSET_ID=<uuid> \
  -e SCAN_JOB_ID=<uuid> \
  -e SUPABASE_URL=https://xxx.supabase.co \
  -e SUPABASE_SERVICE_ROLE_KEY=xxx \
  katana-go:latest
```

## Environment Variables

### Required (All Modes)

| Variable | Description | Example |
|----------|-------------|---------|
| `SCAN_JOB_ID` | Scan job UUID | `123e4567-e89b-12d3-a456-426614174000` |
| `ASSET_ID` | Asset UUID | `123e4567-e89b-12d3-a456-426614174000` |
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service key | `eyJ...` |

### Simple Mode

| Variable | Description | Example |
|----------|-------------|---------|
| `TARGET_URLS` | JSON array or comma-separated URLs | `["https://example.com"]` |

### Batch Mode

| Variable | Description | Example |
|----------|-------------|---------|
| `BATCH_MODE` | Enable batch mode | `true` |
| `BATCH_ID` | Batch job UUID | `123e4567-e89b-12d3-a456-426614174000` |
| `BATCH_OFFSET` | Batch offset | `0` |
| `BATCH_LIMIT` | Batch limit | `20` |

### Streaming Mode

| Variable | Description | Example |
|----------|-------------|---------|
| `STREAMING_MODE` | Enable streaming mode | `true` |
| `REDIS_HOST` | Redis server host | `redis.internal` |
| `REDIS_PORT` | Redis server port | `6379` |
| `REDIS_PASSWORD` | Redis password (optional) | `secret` |
| `STREAM_INPUT_KEY` | Input stream name | `scan:httpx:results` |
| `CONSUMER_GROUP` | Consumer group name | `katana-workers` |
| `CONSUMER_NAME` | Consumer name | `katana-task-1` |

### Optional Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level: `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `CRAWL_DEPTH` | `1` | Maximum crawl depth |
| `HEADLESS_MODE` | `true` | Enable headless Chrome |
| `RATE_LIMIT` | `150` | Max requests per second |
| `CONCURRENCY` | `10` | Parallel crawling workers |
| `PARALLELISM` | `10` | Parallel URL processing |
| `TIMEOUT` | `10` | Request timeout (seconds) |
| `STRATEGY` | `depth-first` | Crawl strategy: `depth-first` or `breadth-first` |

## Logging

The module uses structured logging with contextual metadata:

```
[2024-11-24 10:30:15.123] INFO  [mode=batch scan_job_id=xxx asset_id=yyy] ℹ️  Starting execution
[2024-11-24 10:30:16.456] DEBUG [mode=batch scan_job_id=xxx asset_id=yyy] 🔍 Fetched 15 HTTP probes
[2024-11-24 10:30:45.789] WARN  [mode=batch scan_job_id=xxx asset_id=yyy] ⚠️  Duplicate URL skipped
[2024-11-24 10:35:12.012] INFO  [mode=batch scan_job_id=xxx asset_id=yyy] ℹ️  Crawl completed: 247 endpoints
```

**Log Levels:**
- `DEBUG`: Verbose output for development (disabled in production by default)
- `INFO`: Normal operations (crawl progress, statistics)
- `WARN`: Recoverable issues (duplicates, timeouts, out-of-scope URLs)
- `ERROR`: Critical failures (database errors, configuration issues)

## Building

```bash
# Local build
docker build -t katana-go:latest .

# Build for ECR
docker build -t 123456789.dkr.ecr.us-east-1.amazonaws.com/neobotnet-v2-dev/katana:latest .
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/neobotnet-v2-dev/katana:latest
```

## Development Status

**Phase 3: Container Implementation (In Progress)**

- [x] Project setup
- [x] Configuration parser
- [x] Structured logging
- [x] Data models
- [ ] Database client (Phase 3.2)
- [ ] Deduplication logic (Phase 3.2)
- [ ] Scanner wrapper (Phase 3.2)
- [ ] Simple mode (Phase 3.2)
- [ ] Batch mode (Phase 3.3)
- [ ] Streaming mode (Phase 3.4)

## Module Profile

```sql
module_name: katana
version: 1.0
dependencies: [httpx]
max_batch_size: 20 URLs
estimated_duration: 20 seconds/URL
resource_scaling:
  - Small (1-20 URLs): 1024 CPU, 2048 MB
  - Medium (21-50 URLs): 2048 CPU, 4096 MB
  - Large (51-100 URLs): 4096 CPU, 8192 MB
```

## Database Schema

**Output Table:** `crawled_endpoints`

See `backend/database/migrations/20251124_add_crawled_endpoints.sql` for complete schema.

## License

Part of NeoBot-Net v2 reconnaissance framework.

