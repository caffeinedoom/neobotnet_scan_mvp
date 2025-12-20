# TYVT - VirusTotal Domain Scanner Module

NeoBot-Net v2 scan module for querying VirusTotal's domain API to discover historical URLs.

## Overview

TYVT queries VirusTotal for each subdomain and extracts `undetected_urls` - these are historical URLs that VirusTotal has seen associated with each domain. This is valuable for bug bounty reconnaissance because it reveals:

- Hidden API endpoints
- Legacy paths and parameters
- JavaScript files and resources
- Admin panels and internal paths
- URLs that may not be discoverable through normal crawling

## Architecture

```
HTTPx Stream (resolved subdomains)
    ↓ XREADGROUP
TYVT Module (Consumer)
    ├─ Query VirusTotal API
    ├─ Extract undetected_urls
    ├─ Store in vt_discovered_urls table
    └─ XADD to output stream (for url-resolver/katana)
```

## Features

- **API Key Rotation**: Automatically rotates through multiple VirusTotal API keys
- **Rate Limiting**: Respects VT's 500 requests/day, 15,500/month limits per key
- **Streaming Mode**: Consumes from HTTPx, produces for downstream modules
- **Batch Mode**: Fetches subdomains from database for large-scale scans
- **Proxy Support**: Optional proxy configuration for IP rotation
- **Deduplication**: Skips already-queried subdomains within a scan

## Execution Modes

### Simple Mode (Testing)
```bash
SCAN_JOB_ID="test-123" \
USER_ID="user-456" \
ASSET_ID="asset-789" \
SUBDOMAINS='["api.example.com", "store.example.com"]' \
VT_API_KEYS="key1,key2,key3" \
SUPABASE_URL="https://project.supabase.co" \
SUPABASE_SERVICE_ROLE_KEY="xxx" \
./tyvt-scanner
```

### Batch Mode (Database Fetch)
```bash
BATCH_MODE=true \
BATCH_ID="batch-123" \
ASSET_ID="asset-789" \
BATCH_OFFSET=0 \
BATCH_LIMIT=100 \
SCAN_JOB_ID="test-123" \
USER_ID="user-456" \
VT_API_KEYS="key1,key2,key3" \
SUPABASE_URL="https://project.supabase.co" \
SUPABASE_SERVICE_ROLE_KEY="xxx" \
./tyvt-scanner
```

### Streaming Mode (HTTPx Consumer)
```bash
STREAMING_MODE=true \
STREAM_INPUT_KEY="scan:job-123:httpx:output" \
STREAM_OUTPUT_KEY="scan:job-123:tyvt:output" \
CONSUMER_GROUP_NAME="tyvt-consumers" \
CONSUMER_NAME="tyvt-task-1" \
REDIS_HOST="cache.amazonaws.com" \
REDIS_PORT="6379" \
SCAN_JOB_ID="test-123" \
USER_ID="user-456" \
ASSET_ID="asset-789" \
VT_API_KEYS="key1,key2,key3" \
SUPABASE_URL="https://project.supabase.co" \
SUPABASE_SERVICE_ROLE_KEY="xxx" \
./tyvt-scanner
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SCAN_JOB_ID` | ✅ | Unique scan identifier |
| `USER_ID` | ✅ | User UUID |
| `ASSET_ID` | Batch/Stream | Asset being scanned |
| `VT_API_KEYS` | ✅ | Comma-separated VT API keys |
| `VT_API_KEY` | ✅ | Single VT API key (fallback) |
| `SUPABASE_URL` | ✅ | Database URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Database auth key |
| `REDIS_HOST` | Stream | Redis host |
| `REDIS_PORT` | Stream | Redis port (default: 6379) |
| `STREAM_INPUT_KEY` | Stream | HTTPx output stream key |
| `STREAM_OUTPUT_KEY` | Stream | TYVT output stream key |
| `CONSUMER_GROUP_NAME` | Stream | Redis consumer group |
| `CONSUMER_NAME` | Stream | Consumer instance name |
| `VT_ROTATION_INTERVAL` | Optional | Key rotation interval (default: 15s) |
| `VT_RATE_LIMIT_DELAY` | Optional | Delay between requests (default: 15s) |
| `PROXY_URL` | Optional | Proxy URL for requests |
| `INSECURE_TLS` | Optional | Skip TLS verification |

## Building

```bash
# Build binary
go build -o tyvt-scanner .

# Build Docker image
docker build -t tyvt-go:local .

# Run tests
go test ./...
```

## Database Schema

The module stores results in the `vt_discovered_urls` table:

```sql
CREATE TABLE vt_discovered_urls (
    id UUID PRIMARY KEY,
    scan_job_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    subdomain TEXT NOT NULL,
    url TEXT NOT NULL,
    positives INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    vt_scan_date TEXT,
    source TEXT DEFAULT 'virustotal',
    discovered_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Output Stream Format

When `STREAM_OUTPUT_KEY` is configured, TYVT publishes discovered URLs:

```json
{
    "url": "https://api.example.com/v1/users",
    "subdomain": "api.example.com",
    "asset_id": "asset-uuid",
    "scan_job_id": "job-uuid",
    "source": "virustotal",
    "positives": 0,
    "total": 67,
    "published_at": "2025-12-19T12:00:00Z"
}
```

Completion marker:
```json
{
    "type": "completion",
    "source": "tyvt",
    "scan_job_id": "job-uuid",
    "asset_id": "asset-uuid",
    "total_results": 150,
    "completed_at": "2025-12-19T12:05:00Z"
}
```

## Rate Limiting Considerations

VirusTotal free tier limits:
- 500 requests/day per API key
- 15,500 requests/month per API key
- 4 requests/minute rate limit

With multiple API keys, TYVT automatically rotates to maximize throughput while respecting these limits.

## Pipeline Integration

TYVT fits into the NeoBot-Net pipeline as follows:

```
Subfinder → DNSx → HTTPx → TYVT → URL-Resolver/Katana
                      ↓
              (subdomains)
                      ↓
                    TYVT
                      ↓
            (discovered URLs)
                      ↓
            URL-Resolver / Katana
```

## License

Proprietary - NeoBot-Net Project

