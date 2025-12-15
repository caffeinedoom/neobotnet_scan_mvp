# Katana Test Container Project Plan

**Date:** November 20, 2025  
**Purpose:** Build minimal test container to understand Katana output and integration patterns  
**Status:** Planning Phase  
**Target:** Local testing to analyze output structure before full module implementation

---

## 📋 Executive Summary

This project plan outlines the development of a **minimal Katana test container** to:
1. Understand Katana library output structure (Request/Response fields)
2. Test headless mode with Chromium in containerized environment
3. Analyze crawled data to design optimal database schema
4. Validate non-root user execution for headless Chrome
5. Establish baseline performance metrics (memory, CPU, execution time)

**Approach:** Build a simplified container that crawls 3-5 test URLs and outputs raw JSON, allowing us to study the data structure before committing to a full module implementation.

---

## 🎯 Objectives

### Primary Objectives
1. **Library Integration:** Successfully use Katana Go library in containerized environment
2. **Headless Mode Validation:** Confirm Chromium + non-root user works in Alpine Linux
3. **Output Analysis:** Capture and study Katana's output.Result structure
4. **Performance Baseline:** Measure resource usage for future capacity planning

### Secondary Objectives
1. **Error Handling:** Identify common failure modes (Chrome crashes, timeouts)
2. **Scope Control:** Test apex domain filtering effectiveness
3. **Extension Filtering:** Validate static asset exclusion works as expected

---

## 🏗️ Architecture Overview

### Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Katana Test Container (Alpine Linux)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Non-Root User: katana (UID 1001)                     │  │
│  │   • Required for headless Chrome execution           │  │
│  │   • Security best practice                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Chromium Browser (Headless)                          │  │
│  │   • Installed via apk (Alpine package)               │  │
│  │   • Path: /usr/bin/chromium-browser                  │  │
│  │   • Flags: --no-sandbox (required for containers)    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Katana Test Binary (Go)                              │  │
│  │   • Simple CLI: accepts URLs via env variable        │  │
│  │   • Configuration: MaxDepth=1, Headless=true         │  │
│  │   • Output: JSON to stdout + file                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Execution Flow

```
1. Docker Run
   └─> Load URLs from environment variable (TEST_URLS)
       └─> Parse JSON array: ["https://example.com", ...]

2. Initialize Katana
   └─> Create Options with:
       • MaxDepth: 1
       • Headless: true
       • UseInstalledChrome: true
       • SystemChromePath: /usr/bin/chromium-browser
       • HeadlessNoSandbox: true (container requirement)
       • Scope: apex domains from URLs

3. Start Crawling
   └─> For each URL:
       ├─> Launch Chromium in headless mode
       ├─> Render JavaScript
       ├─> Extract links, forms, endpoints
       └─> Call OnResult callback

4. Output Collection
   └─> OnResult callback writes to:
       ├─> Stdout (for docker logs)
       └─> JSON file (/output/results.json)

5. Analysis
   └─> Study output structure:
       ├─> Request fields (URL, Method, Headers, Depth)
       ├─> Response fields (StatusCode, Body, Technologies, Forms)
       └─> Identify database schema requirements
```

---

## 📁 Project Structure

```
/root/pluckware/neobotnet/neobotnet_v2/
└── backend/containers/katana-test/
    ├── main.go                    # Entry point - minimal implementation
    ├── Dockerfile                 # Multi-stage build with Chromium
    ├── go.mod                     # Dependencies (katana + supporting libs)
    ├── go.sum                     # Dependency lock file
    ├── README.md                  # Usage instructions
    ├── test_urls.json             # Sample URLs for testing
    └── output/                    # Output directory (mounted volume)
        └── results.json           # Captured Katana output
```

---

## 🔧 Implementation Details

### Phase 1: Dockerfile Configuration

**Goal:** Create a secure, minimal container with Chromium + Katana

**Key Requirements:**
1. **Multi-stage build** to minimize image size
2. **Chromium installation** for headless mode
3. **Non-root user** (UID 1001) for Chrome security model
4. **Proper permissions** on output directory

**Dockerfile Strategy:**

```dockerfile
# Stage 1: Builder
FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git ca-certificates build-base
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY main.go ./
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o katana-test .

# Stage 2: Production
FROM alpine:latest

# Install Chromium and runtime dependencies
RUN apk add --no-cache \
    ca-certificates \
    chromium \
    chromium-chromedriver \
    bash \
    curl

# Create non-root user for Chrome
RUN addgroup -g 1001 katana && \
    adduser -D -u 1001 -G katana katana

# Create output directory with proper permissions
RUN mkdir -p /app/output && \
    chown -R katana:katana /app

WORKDIR /app
COPY --from=builder /app/katana-test .

# Switch to non-root user (CRITICAL for headless mode)
USER katana

# Set Chromium path for Katana
ENV CHROME_BIN=/usr/bin/chromium-browser \
    CHROME_PATH=/usr/bin/chromium-browser

ENTRYPOINT ["./katana-test"]
```

**Critical Configuration Notes:**
- **`USER katana`**: Chrome refuses to run as root for security
- **`--no-sandbox`**: Required flag for containerized Chrome (security trade-off)
- **`chromium-chromedriver`**: Optional but useful for debugging

---

### Phase 2: Minimal Go Implementation

**Goal:** Simplest possible Katana integration to capture output

**main.go Structure:**

```go
package main

import (
    "encoding/json"
    "fmt"
    "log"
    "math"
    "os"
    
    "github.com/projectdiscovery/gologger"
    "github.com/projectdiscovery/katana/pkg/engine/hybrid"
    "github.com/projectdiscovery/katana/pkg/output"
    "github.com/projectdiscovery/katana/pkg/types"
)

// ResultCapture stores all crawled results for analysis
type ResultCapture struct {
    Results []output.Result `json:"results"`
    Stats   Stats           `json:"stats"`
}

type Stats struct {
    TotalURLs      int `json:"total_urls"`
    UniqueEndpoints int `json:"unique_endpoints"`
    FormCount      int `json:"form_count"`
    DepthMax       int `json:"depth_max"`
}

func main() {
    log.Println("🕷️ Katana Test Container - v0.1")
    
    // 1. Load test URLs from environment
    urlsJSON := os.Getenv("TEST_URLS")
    if urlsJSON == "" {
        log.Fatal("❌ TEST_URLS environment variable required")
    }
    
    var urls []string
    if err := json.Unmarshal([]byte(urlsJSON), &urls); err != nil {
        log.Fatalf("❌ Failed to parse TEST_URLS: %v", err)
    }
    
    log.Printf("📋 Testing with %d URLs", len(urls))
    
    // 2. Initialize result collector
    capture := &ResultCapture{
        Results: []output.Result{},
        Stats:   Stats{},
    }
    
    // 3. Configure Katana options
    options := &types.Options{
        // Crawling Strategy
        MaxDepth:     1,                    // Shallow crawl for testing
        Strategy:     "depth-first",
        FieldScope:   "rdn",                // Registered Domain Name
        
        // Performance (conservative for testing)
        Concurrency:  2,
        Parallelism:  2,
        Timeout:      30,
        Delay:        0,
        RateLimit:    50,
        
        // Headless Configuration
        Headless:           true,
        UseInstalledChrome: true,
        SystemChromePath:   "/usr/bin/chromium-browser",
        HeadlessNoSandbox:  true,          // REQUIRED for containers
        
        // JavaScript Parsing
        ScrapeJSResponses: true,           // Parse JS files
        
        // Extension Filtering (match your command)
        ExtensionFilter: []string{
            ".css", ".jpg", ".jpeg", ".png", ".svg", ".gif",
            ".mp4", ".woff", ".woff2", ".ttf", ".eot",
        },
        
        // Output Configuration
        JSON:      true,
        NoColors:  true,
        Silent:    false,
        Verbose:   true,                   // Debug mode for testing
        
        // Callback for each discovered endpoint
        OnResult: func(result output.Result) {
            // Store result for analysis
            capture.Results = append(capture.Results, result)
            
            // Log to console
            if result.Request != nil {
                log.Printf("🔗 Found: %s (Depth: %d)", 
                    result.Request.URL, 
                    result.Request.Depth)
            }
            
            // Update stats
            capture.Stats.TotalURLs++
            if result.Request != nil && result.Request.Depth > capture.Stats.DepthMax {
                capture.Stats.DepthMax = result.Request.Depth
            }
            if result.Response != nil && len(result.Response.Forms) > 0 {
                capture.Stats.FormCount += len(result.Response.Forms)
            }
        },
    }
    
    // 4. Create crawler
    crawlerOptions, err := types.NewCrawlerOptions(options)
    if err != nil {
        log.Fatalf("❌ Failed to create crawler options: %v", err)
    }
    defer crawlerOptions.Close()
    
    // Use hybrid crawler (headless mode)
    crawler, err := hybrid.New(crawlerOptions)
    if err != nil {
        log.Fatalf("❌ Failed to create crawler: %v", err)
    }
    defer crawler.Close()
    
    // 5. Crawl each URL
    for i, url := range urls {
        log.Printf("\n📍 Crawling [%d/%d]: %s", i+1, len(urls), url)
        
        if err := crawler.Crawl(url); err != nil {
            log.Printf("⚠️ Crawl failed for %s: %v", url, err)
            continue
        }
    }
    
    // 6. Save results to file
    capture.Stats.UniqueEndpoints = len(capture.Results)
    
    outputFile := "/app/output/results.json"
    data, err := json.MarshalIndent(capture, "", "  ")
    if err != nil {
        log.Fatalf("❌ Failed to marshal results: %v", err)
    }
    
    if err := os.WriteFile(outputFile, data, 0644); err != nil {
        log.Fatalf("❌ Failed to write output file: %v", err)
    }
    
    // 7. Print summary
    log.Println("\n" + "═" * 60)
    log.Println("📊 CRAWL SUMMARY")
    log.Println("═" * 60)
    log.Printf("Total URLs Discovered: %d", capture.Stats.TotalURLs)
    log.Printf("Unique Endpoints: %d", capture.Stats.UniqueEndpoints)
    log.Printf("Forms Found: %d", capture.Stats.FormCount)
    log.Printf("Max Depth Reached: %d", capture.Stats.DepthMax)
    log.Printf("Output saved to: %s", outputFile)
    log.Println("✅ Test completed successfully!")
}
```

**Key Implementation Decisions:**

1. **Minimal Complexity:** No database, no Redis - just pure crawling
2. **Result Capture:** Store ALL output.Result structs for analysis
3. **Statistics Tracking:** Basic metrics to understand crawl behavior
4. **Verbose Logging:** Debug information for troubleshooting
5. **File Output:** JSON file for offline analysis

---

### Phase 3: Testing Strategy

**Test Environment:** Local Docker on VPS (http://172.236.127.72)

**Test URLs (Production - Nubank):**

```json
[
  "https://blog.nubank.com.br/",
  "https://clojure-south.nubank.com.br/",
  "https://keygen.share.nubank.com.br/"
]
```

**Why These URLs?**
- **blog.nubank.com.br**: Real blog with articles, categories, pagination (comprehensive link structure)
- **clojure-south.nubank.com.br**: Event/conference page (likely has forms, registration)
- **keygen.share.nubank.com.br**: Key generation tool (likely has forms, API endpoints)
- **Benefit**: All share same apex domain (nubank.com.br) - perfect for testing scope control

**Test Execution Steps:**

```bash
# 1. Build test container
cd /root/pluckware/neobotnet/neobotnet_v2/backend/containers/katana-test
docker build -t katana-test:v0.1 .

# 2. Create output directory
mkdir -p output

# 3. Run test with Nubank URLs
docker run --rm \
  -e TEST_URLS='["https://blog.nubank.com.br/","https://clojure-south.nubank.com.br/","https://keygen.share.nubank.com.br/"]' \
  -v $(pwd)/output:/app/output \
  katana-test:v0.1

# 4. Inspect output
cat output/results.json | jq '.stats'
cat output/results.json | jq '.results[0]' > sample_result.json

# 5. Analyze structure
cat sample_result.json | jq 'keys'
```

**Expected Output Structure:**

Based on Katana library source code, we expect:

```json
{
  "results": [
    {
      "timestamp": "2025-11-20T10:30:00Z",
      "request": {
        "method": "GET",
        "endpoint": "https://example.com/about",
        "depth": 1,
        "source": "https://example.com",
        "tag": "a",
        "attribute": "href"
      },
      "response": {
        "status_code": 200,
        "headers": {
          "content-type": "text/html"
        },
        "body": "...",
        "content_length": 1256,
        "technologies": ["Nginx"],
        "forms": [
          {
            "method": "POST",
            "action": "/contact",
            "enctype": "multipart/form-data",
            "parameters": ["name", "email", "message"]
          }
        ]
      }
    }
  ],
  "stats": {
    "total_urls": 45,
    "unique_endpoints": 45,
    "form_count": 3,
    "depth_max": 1
  }
}
```

---

## 📊 Analysis Plan

### Output Analysis Objectives

Once we have raw output, we will analyze:

#### 1. **Request Structure Analysis**
- **Fields:** method, endpoint, depth, source, tag, attribute
- **Database Mapping:** Which fields should be indexed?
- **Query Patterns:** How will we search this data?

#### 2. **Response Structure Analysis**
- **Essential Fields:** status_code, content_type, content_length
- **Optional Fields:** body (storage implications), headers (JSONB?)
- **Technology Detection:** Store technologies array?
- **Forms:** Extract parameters for fuzzing/testing?

#### 3. **Relationship Mapping**
- **Parent-Child:** How to link discovered URL to source URL?
- **Domain Hierarchy:** Connect to subdomains table?
- **Scan Tracking:** Link to scan_job_id?

#### 4. **Deduplication Strategy**
**Question to Answer:** Per-scan or global deduplication?

**Option A: Per-Scan Deduplication**
```sql
CONSTRAINT unique_endpoint_per_scan UNIQUE (scan_job_id, url)
```
- **Pros:** Tracks URL discovery across different scans
- **Cons:** Duplicate storage if URL found in multiple scans

**Option B: Global Deduplication**
```sql
CONSTRAINT unique_endpoint_global UNIQUE (url)
-- Then: many-to-many table for scan_job_id relationships
```
- **Pros:** Minimal storage, single source of truth
- **Cons:** Loses per-scan context (when was it discovered?)

**Recommendation:** After seeing real data volume, we'll decide. Likely **Option A** (per-scan) for tracking changes over time.

#### 5. **Storage Optimization**
- **Body Storage:** Full HTML vs. excerpt vs. omit?
  - **Full:** Complete data but 1MB+ per page
  - **Excerpt:** First 10KB (enough for preview)
  - **Omit:** No storage (just metadata)
- **Header Storage:** Store as JSONB or only important headers?
- **Technology Detection:** Worth storing? (useful for targeting)

---

## 🚨 Risk Assessment & Mitigation

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Chrome crashes in container** | High | Medium | Test with `--no-sandbox`, allocate sufficient memory (2GB+) |
| **Permissions issues (non-root)** | High | Medium | Ensure `/app/output` owned by katana user, test volume mounts |
| **Out of memory (OOM Kill)** | High | High | Start with small test URLs, monitor with `docker stats` |
| **Chromium installation fails** | High | Low | Use Alpine's official chromium package, verify in Dockerfile |
| **Katana library version mismatch** | Medium | Low | Pin version in go.mod: `v1.2.2` |
| **Timeout on slow sites** | Low | Medium | Set aggressive timeout (30s), accept failures for testing |

### Operational Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Container image too large** | Medium | Multi-stage build, alpine base (~200MB expected) |
| **Test URLs return 403/captcha** | Low | Use well-known test sites, avoid production targets |
| **Output file too large** | Low | Limit test to 3-5 URLs max |

---

## 📝 Success Criteria

### Phase 1: Container Build ✅
- [ ] Dockerfile builds without errors
- [ ] Image size < 300MB
- [ ] Chromium binary exists at `/usr/bin/chromium-browser`
- [ ] Non-root user `katana` created (UID 1001)
- [ ] Go binary builds successfully

### Phase 2: Execution ✅
- [ ] Container starts without errors
- [ ] Chromium launches in headless mode
- [ ] At least 1 URL crawls successfully
- [ ] OnResult callback triggers (logs visible)
- [ ] No segmentation faults or crashes
- [ ] Container exits cleanly

### Phase 3: Output Validation ✅
- [ ] `results.json` file created in `/app/output`
- [ ] JSON is valid (parseable by `jq`)
- [ ] Contains expected fields: `request`, `response`, `timestamp`
- [ ] Stats show reasonable numbers (depth=1, >0 URLs found)
- [ ] Forms extracted (if present on test sites)
- [ ] Technologies detected (if Wappalyzer patterns match)

### Phase 4: Analysis Completion ✅
- [ ] Database schema drafted based on output structure
- [ ] Deduplication strategy decided
- [ ] Storage optimization approach chosen
- [ ] Performance baseline documented (memory, CPU, time)
- [ ] Known issues list created

---

## 🗓️ Timeline & Next Steps

### Immediate (Today - Nov 20)
1. **Create project structure** (5 min)
   - `mkdir -p backend/containers/katana-test`
   - Create files: main.go, Dockerfile, go.mod

2. **Implement Dockerfile** (20 min)
   - Multi-stage build
   - Chromium installation
   - Non-root user setup

3. **Implement main.go** (30 min)
   - Basic Katana integration
   - Result capture logic
   - File output

4. **Build and test locally** (30 min)
   - `docker build`
   - `docker run` with test URLs
   - Validate output

5. **Analyze output** (45 min)
   - Study result structure
   - Document findings
   - Draft database schema

### Follow-up (Next Session)
1. **Refine based on findings**
2. **Design final database schema**
3. **Plan full module implementation**
4. **Create module profile for database**

---

## 📚 Reference Materials

### Katana Library Documentation
- **Installed Path:** `/root/go/pkg/mod/github.com/projectdiscovery/katana@v1.2.2`
- **Key Files:**
  - `pkg/types/options.go` - Configuration options
  - `pkg/output/result.go` - Output structure
  - `pkg/navigation/request.go` - Request details
  - `pkg/navigation/response.go` - Response details
  - `pkg/engine/hybrid/hybrid.go` - Headless crawler
  - `Dockerfile` - Official Katana container reference

### Existing Module References
- **Subfinder:** `/root/pluckware/neobotnet/neobotnet_v2/backend/containers/subfinder-go/`
- **HTTPx:** `/root/pluckware/neobotnet/neobotnet_v2/backend/containers/httpx-go/`
- **DNSx:** `/root/pluckware/neobotnet/neobotnet_v2/backend/containers/dnsx-go/`

### Template Documentation
- `/root/pluckware/neobotnet/neobotnet_v2/docs/proper/03-IMPLEMENTING-A-MODULE.md`
- `/root/pluckware/neobotnet/neobotnet_v2/docs/proper/02-MODULE-SYSTEM.md`

---

## 🔍 Key Questions to Answer

### During Testing
1. **Memory Usage:** How much RAM does headless Chrome consume per URL?
2. **Execution Time:** How long to crawl 1 URL at depth-1?
3. **Discovery Rate:** How many endpoints found per seed URL?
4. **Error Rate:** What percentage of URLs fail to crawl?
5. **Chromium Stability:** Does Chrome crash? How often?

### During Analysis
1. **Field Completeness:** Are all expected fields populated?
2. **Data Quality:** Is body/header content useful for security analysis?
3. **Form Extraction:** Are form parameters correctly identified?
4. **Technology Detection:** Are technologies accurately detected?
5. **Scope Adherence:** Does Katana stay within defined scope?

---

## 📈 Expected Outcomes

### Technical Deliverables
1. **Working Test Container:** Functional Katana container with headless mode
2. **Sample Output:** Real-world JSON output from 3-5 test URLs
3. **Analysis Report:** Document findings and recommendations
4. **Database Schema Draft:** Proposed `crawled_endpoints` table structure
5. **Performance Metrics:** Baseline resource usage data

### Knowledge Gained
1. **Library Familiarity:** Hands-on experience with Katana Go API
2. **Container Complexity:** Understanding of headless Chrome requirements
3. **Output Structure:** Deep understanding of available data fields
4. **Integration Challenges:** Identify potential issues early
5. **Cost Estimation:** Data for resource planning

---

## 🎯 Decision Points

### After Test Completion, Decide:

1. **Headless Mode Default?**
   - If stable: Yes (comprehensive coverage)
   - If crashes frequently: Make optional

2. **Body Storage?**
   - If < 50KB avg: Store full body
   - If > 50KB avg: Store excerpt or omit

3. **Batch Size?**
   - If < 1GB memory: 20 URLs/batch
   - If > 1GB memory: Reduce to 10 URLs/batch

4. **Depth Default?**
   - If fast (< 2min/URL): Increase to depth-2
   - If slow (> 5min/URL): Keep depth-1

5. **Technology Detection?**
   - If useful data: Enable by default
   - If noisy: Make optional

---

## ✅ Approval & Sign-off

**Created By:** AI Assistant (Claude Sonnet 4.5)  
**Reviewed By:** Sam (Pluckware)  
**Approved:** [Pending]  
**Status:** Ready for Implementation  

**Next Action:** Proceed with Dockerfile and main.go implementation

---

## 📎 Appendix

### A. Go Module Dependencies

```go
module katana-test

go 1.21

require (
    github.com/projectdiscovery/katana v1.2.2
    github.com/projectdiscovery/gologger v1.1.8
)
```

### B. Sample Test URLs File

```json
{
  "test_urls": [
    "https://blog.nubank.com.br/",
    "https://clojure-south.nubank.com.br/",
    "https://keygen.share.nubank.com.br/"
  ],
  "notes": "Real production Nubank sites for comprehensive testing"
}
```

### C. Docker Build Command Reference

```bash
# Build
docker build -t katana-test:v0.1 .

# Run with Nubank test URLs
docker run --rm \
  --name katana-test \
  -e TEST_URLS='["https://blog.nubank.com.br/","https://clojure-south.nubank.com.br/","https://keygen.share.nubank.com.br/"]' \
  -v $(pwd)/output:/app/output \
  katana-test:v0.1

# Run with debugging
docker run --rm -it \
  --name katana-test-debug \
  -e TEST_URLS='["https://example.com"]' \
  -v $(pwd)/output:/app/output \
  --entrypoint /bin/sh \
  katana-test:v0.1

# Monitor resource usage
docker stats katana-test
```

### D. Output Analysis Commands

```bash
# Pretty print JSON
cat output/results.json | jq '.'

# Count total results
cat output/results.json | jq '.results | length'

# Show unique endpoints
cat output/results.json | jq '.results[].request.endpoint' | sort -u

# Extract forms
cat output/results.json | jq '.results[].response.forms[]'

# Show technologies
cat output/results.json | jq '.results[].response.technologies[]' | sort -u

# Check file size
du -h output/results.json
```

---

**Document Version:** 1.0  
**Last Updated:** November 20, 2025  
**Location:** `/root/pluckware/neobotnet/neobotnet_v2/docs/scan_modules/katana/nov20/`
