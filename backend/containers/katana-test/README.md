# Katana Test Container

**Purpose:** Test Katana crawler with real URLs to analyze output structure and inform database schema design.

## 🎯 What This Container Does

This test container runs Katana in headless mode and generates **multiple output formats** for comprehensive data quality analysis:

1. **`results_raw.json`** - All discoveries (including duplicates)
2. **`results_deduplicated.json`** - Unique URLs only (in-memory dedup)
3. **`database_mock.csv`** - PostgreSQL table preview
4. **`analysis_report.json`** - Duplication statistics and filtering recommendations

## 🚀 Quick Start

### Build the Container

```bash
cd /root/pluckware/neobotnet/neobotnet_v2/backend/containers/katana-test
docker build -t katana-test:latest .
```

### Run Test (60 seconds, default URLs)

```bash
docker run --rm -v $(pwd)/output:/app/output katana-test:latest
```

### Run Custom Test

```bash
# Custom duration (5 minutes)
docker run --rm \
  -e TEST_DURATION_SECONDS=300 \
  -e TEST_URLS="https://blog.nubank.com.br/,https://clojure-south.nubank.com.br/" \
  -v $(pwd)/output:/app/output \
  katana-test:latest
```

## 📊 Output Files

After running, check `./output/` directory:

### 1. `results_raw.json`
Complete crawl data including all duplicates.

```json
{
  "results": [/* All Katana discoveries */],
  "stats": {
    "total_urls": 9,
    "unique_endpoints": 8,
    "duplication_rate": "11%"
  }
}
```

### 2. `results_deduplicated.json`
Unique URLs only with discovery metadata.

```json
{
  "results": [
    {
      "url": "https://blog.nubank.com.br/",
      "url_hash": "abc123...",
      "status_code": 200,
      "content_type": "text/html",
      "first_seen_at": "2025-11-20T22:42:27Z",
      "last_seen_at": "2025-11-20T22:42:41Z",
      "times_discovered": 2
    }
  ]
}
```

### 3. `database_mock.csv`
Simulated PostgreSQL table (how data would be stored).

```csv
asset_id,url,url_hash,method,status_code,content_type,first_seen_at,times_discovered
1,https://blog.nubank.com.br/,abc123...,GET,200,text/html,2025-11-20T22:42:27Z,2
```

### 4. `analysis_report.json`
Comprehensive analysis with filtering recommendations.

```json
{
  "summary": {
    "total_discoveries": 9,
    "unique_urls": 8,
    "duplication_rate": "11%"
  },
  "duplicates": {
    "https://blog.nubank.com.br/": {
      "times_found": 2,
      "reason": "Discovered multiple times (likely self-referential)"
    }
  },
  "filtering_recommendations": {
    "self_referential_candidates": 1,
    "failed_requests": 2,
    "suggested_filters": [
      "Deduplicate within scan (1 URLs found multiple times, 11% reduction)",
      "Consider filtering failed requests (2 URLs with null status)"
    ]
  }
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_DURATION_SECONDS` | `120` | How long to crawl (in seconds) |
| `TEST_URLS` | Nubank URLs | Comma-separated list of seed URLs |
| `CRAWL_DEPTH` | `1` | Maximum crawl depth |

### Examples

```bash
# Quick 2-minute test
docker run --rm \
  -e TEST_DURATION_SECONDS=120 \
  -v $(pwd)/output:/app/output \
  katana-test:latest

# Deep 10-minute crawl
docker run --rm \
  -e TEST_DURATION_SECONDS=600 \
  -e CRAWL_DEPTH=2 \
  -v $(pwd)/output:/app/output \
  katana-test:latest

# Custom URLs
docker run --rm \
  -e TEST_URLS="https://example.com/,https://test.com/" \
  -v $(pwd)/output:/app/output \
  katana-test:latest
```

## 📈 Understanding the Output

### Deduplication Logic

The container performs **URL normalization** before hashing:
- Lowercase hostname
- Remove fragments (`#section`)
- Sort query parameters
- Remove trailing slashes (except root `/`)

**Example:**
```
https://EXAMPLE.com/page?b=2&a=1#top
→ Normalized: https://example.com/page?a=1&b=2
→ SHA256 hash: abc123...
```

### Status Code Distribution

```json
"status_distribution": {
  "200": 5,   // Successful
  "404": 2,   // Not found
  "null": 2   // Failed requests (network errors)
}
```

### Content Type Distribution

```json
"content_type_distribution": {
  "text/html": 7,
  "application/javascript": 1
}
```

## 🧪 Testing Workflow

### Step 1: Run Initial Test
```bash
docker run --rm -v $(pwd)/output:/app/output katana-test:latest
```

### Step 2: Review Analysis
```bash
# Quick summary
cat output/analysis_report.json | jq '.summary'

# Check duplicates
cat output/analysis_report.json | jq '.duplicates'

# Filtering recommendations
cat output/analysis_report.json | jq '.filtering_recommendations'
```

### Step 3: Examine Database Mock
```bash
# View CSV
cat output/database_mock.csv

# Or use column for better formatting
column -t -s, output/database_mock.csv | less -S
```

### Step 4: Make Decisions
Based on the analysis:
- Is deduplication needed? (Check `duplication_rate`)
- Should we filter failed requests? (Check `failed_requests`)
- What status codes matter? (Check `status_distribution`)

## 🎯 Use Cases

### Case 1: Validate Storage Estimates
Run a 5-minute test to project production storage needs:
```bash
docker run --rm \
  -e TEST_DURATION_SECONDS=300 \
  -e TEST_URLS="https://your-target.com/" \
  -v $(pwd)/output:/app/output \
  katana-test:latest

# Then check:
# - Total unique URLs found
# - Multiply by estimated assets
# - = Storage projection
```

### Case 2: Test Filtering Strategies
Compare raw vs. deduplicated results to see filtering impact:
```bash
# After running:
echo "Raw discoveries: $(cat output/results_raw.json | jq '.results | length')"
echo "Unique URLs: $(cat output/results_deduplicated.json | jq '.results | length')"
echo "Reduction: $(cat output/analysis_report.json | jq -r '.summary.duplication_rate')"
```

### Case 3: Analyze Target Behavior
Different sites have different patterns:
- **SPAs (React/Next.js):** High duplication (navigation links everywhere)
- **Traditional sites:** Lower duplication
- **APIs:** Very low duplication (REST endpoints)

## 🐛 Debugging

### Container Logs
```bash
docker run --rm \
  -v $(pwd)/output:/app/output \
  katana-test:latest 2>&1 | tee crawl.log
```

### Check Chromium
```bash
# Verify chromium works
docker run --rm katana-test:latest chromium-browser --version
```

### Verify Output Files
```bash
ls -lh output/
# Should see: results_raw.json, results_deduplicated.json, database_mock.csv, analysis_report.json
```

## 📚 Architecture

```
main.go
├─ Katana Setup (hybrid engine, headless mode)
├─ Result Capture (in-memory collection)
├─ Signal Handling (graceful shutdown)
└─ Output Generation
   ├─ Raw JSON (all discoveries)
   ├─ Deduplication (URL normalization + hashing)
   ├─ CSV Mock (database preview)
   └─ Analysis Report (recommendations)
```

### Key Functions

- **`normalizeURL()`** - URL normalization for consistent hashing
- **`hashURL()`** - SHA256 hash generation
- **`deduplicateResults()`** - In-memory deduplication
- **`generateAnalysisReport()`** - Statistics and recommendations
- **`saveCSVMock()`** - Database table simulation

## 🔒 Security Notes

- Runs as non-root user (`katana`)
- Chromium with `--no-sandbox` (required for containers)
- No network access outside crawled domains (controlled by scope)

## 📖 Next Steps

After analyzing test output:
1. Review `analysis_report.json` recommendations
2. Decide on filtering strategy
3. Design database schema based on `database_mock.csv`
4. Implement full Katana module for production

## 🤝 Contributing

This is a test container - modify freely for your needs!

**Common modifications:**
- Adjust `TimeStable` for faster/slower crawling
- Change `MaxDepth` for deeper discovery
- Modify `Concurrency` for speed
- Add custom filters in `OnResult` callback

---

**Last Updated:** November 21, 2025  
**Version:** 2.0 (Multi-format output with analysis)
