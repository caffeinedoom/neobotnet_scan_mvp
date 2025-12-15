# Module Implementation Guide

**Step-by-Step Tutorial for Adding New Modules**

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Implementation Steps Overview](#implementation-steps-overview)
3. [Step 1: Database Configuration](#step-1-database-configuration)
4. [Step 2: Container Implementation](#step-2-container-implementation)
5. [Step 3: Database Integration](#step-3-database-integration)
6. [Step 4: Redis Streaming (Optional)](#step-4-redis-streaming-optional)
7. [Step 5: ECS Task Definition](#step-5-ecs-task-definition)
8. [Step 6: Testing](#step-6-testing)
9. [Step 7: Deployment](#step-7-deployment)
10. [Reference Implementations](#reference-implementations)

---

## Prerequisites

**Knowledge Requirements**:
- Go programming (modules, error handling, concurrency)
- Docker (Dockerfile, multi-stage builds)
- PostgreSQL (SQL, JSONB, transactions)
- Redis Streams (XADD, XREADGROUP, consumer groups)
- AWS ECS (Fargate, task definitions, IAM roles)

**Tools Required**:
- Go 1.21+
- Docker 24+
- AWS CLI configured
- Database access (Supabase or PostgreSQL)
- Redis CLI (for testing)

**Existing Modules** (reference implementations):
- **Subfinder**: Producer pattern (streams output)
- **DNSx**: Consumer pattern (reads stream, batch database fetch)
- **HTTPx**: Consumer pattern (reads stream, HTTP probing)

---

## Implementation Steps Overview

**High-Level Process** (complete module in ~2-4 hours):

```
1. Database Config (10 min)    → Insert module profile into scan_module_profiles
2. Container Code (90 min)     → Implement main.go, scanner.go, database.go
3. Dockerfile (10 min)         → Multi-stage build with Go binary
4. Task Definition (15 min)    → Terraform or AWS Console
5. Testing (30 min)            → Local Docker → VPS → Cloud
6. Deployment (15 min)         → Push to ECR, register task definition
```

---

## Step 1: Database Configuration

### 1.1: Determine Module Characteristics

**Questions to Answer**:

| Question | Answer | Impact |
|----------|--------|--------|
| Does it have dependencies? | Yes: `[subfinder]` | Must fetch data from DB |
| Does it produce intermediate results? | Yes (nuclei findings) | Should stream to Redis |
| What's the workload size? | 10-100 domains | Determines resource scaling |
| What's the time per domain? | ~30 seconds | Sets `estimated_duration_per_domain` |

**Example: Nuclei Module**:
- **Purpose**: Vulnerability scanning
- **Dependencies**: `[httpx]` (needs HTTP probes)
- **Streaming**: Yes (findings should be real-time)
- **Batching**: Yes (scan 50 URLs per task)
- **Resources**: High CPU/memory (template matching)

### 1.2: Insert Module Profile

**SQL Template**:

```sql
INSERT INTO scan_module_profiles (
    module_name,
    version,
    supports_batching,
    max_batch_size,
    resource_scaling,
    estimated_duration_per_domain,
    task_definition_template,
    container_name,
    dependencies,
    optimization_hints,
    is_active
) VALUES (
    'nuclei',  -- ① Module name (lowercase, no spaces)
    '1.0',     -- ② Version (semantic versioning)
    true,      -- ③ Supports batching?
    50,        -- ④ Max URLs per batch
    '{
        "domain_count_ranges": [
            {"min_domains": 1, "max_domains": 10, "cpu": 1024, "memory": 2048, "description": "Light scan"},
            {"min_domains": 11, "max_domains": 30, "cpu": 2048, "memory": 4096, "description": "Medium scan"},
            {"min_domains": 31, "max_domains": 50, "cpu": 4096, "memory": 8192, "description": "Heavy scan"}
        ],
        "scaling_notes": "Nuclei is CPU-intensive. Template matching dominates execution time."
    }'::jsonb,  -- ⑤ Resource scaling (JSONB)
    30,         -- ⑥ Seconds per domain
    'neobotnet-v2-dev-nuclei',  -- ⑦ ECS task definition family
    'nuclei-scanner',           -- ⑧ Container name
    ARRAY['httpx'],             -- ⑨ Dependencies
    '{
        "requires_database_fetch": true,
        "requires_asset_id": true,
        "streams_output": true,
        "high_cpu_usage": true,
        "high_memory_usage": true,
        "template_count": 3000,
        "severity_filters": ["critical", "high", "medium"]
    }'::jsonb,  -- ⑩ Optimization hints
    true        -- ⑪ Active?
);
```

**Verification**:

```sql
-- Confirm module registered
SELECT module_name, version, supports_batching, is_active 
FROM scan_module_profiles 
WHERE module_name = 'nuclei';

-- Check dependencies
SELECT module_name, dependencies 
FROM scan_module_profiles 
WHERE module_name = 'nuclei';
-- Expected: {httpx}
```

---

## Step 2: Container Implementation

### 2.1: Directory Structure

```
backend/containers/nuclei-go/
├── main.go              # Entry point, mode routing
├── scanner.go           # Core scanning logic
├── database.go          # Supabase/PostgreSQL integration
├── streaming.go         # Redis Streams consumer (if needed)
├── batch_support.go     # Batch mode logic
├── Dockerfile           # Multi-stage build
├── go.mod               # Go dependencies
└── go.sum               # Checksums
```

### 2.2: Main Entry Point (`main.go`)

**Template Pattern**:

```go
package main

import (
    "log"
    "os"
)

// TEMPLATE PATTERN: Environment Variable Validation
func validateRequiredEnvVars(batchMode, streamingMode bool) error {
    required := []string{
        "SCAN_JOB_ID",
        "USER_ID",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    }
    
    if batchMode {
        required = append(required, "BATCH_ID", "ASSET_ID", "BATCH_OFFSET", "BATCH_LIMIT")
    } else if streamingMode {
        required = append(required, "STREAM_INPUT_KEY", "CONSUMER_GROUP_NAME", "CONSUMER_NAME")
    } else {
        required = append(required, "DOMAINS")
    }
    
    var missing []string
    for _, key := range required {
        if os.Getenv(key) == "" {
            missing = append(missing, key)
        }
    }
    
    if len(missing) > 0 {
        return fmt.Errorf("missing required environment variables: %v", missing)
    }
    
    return nil
}

// TEMPLATE PATTERN: Main Function (Mode Routing)
func main() {
    // 1. Determine execution mode
    batchMode := os.Getenv("BATCH_MODE") == "true"
    streamingMode := os.Getenv("STREAMING_MODE") == "true"
    
    log.Printf("🚀 Nuclei Scanner starting...")
    
    var executionMode string
    if streamingMode {
        executionMode = "STREAMING (Consumer)"
    } else if batchMode {
        executionMode = "BATCH"
    } else {
        executionMode = "SIMPLE"
    }
    log.Printf("📋 Execution mode: %s", executionMode)
    
    // 2. Validate environment
    if err := validateRequiredEnvVars(batchMode, streamingMode); err != nil {
        log.Fatalf("❌ Environment validation failed: %v", err)
    }
    
    log.Println("✅ Environment validation passed")
    
    // 3. Route to appropriate handler
    var err error
    if streamingMode {
        err = runStreamingMode()
    } else if batchMode {
        err = runBatchMode()
    } else {
        err = runSimpleMode()
    }
    
    if err != nil {
        log.Fatalf("❌ Execution failed: %v", err)
    }
    
    log.Println("✅ Nuclei scan completed successfully")
}
```

### 2.3: Simple Mode Implementation

**For Producers (Subfinder pattern)**:

```go
// TEMPLATE PATTERN: Simple Mode (Producer)
func runSimpleMode() error {
    // 1. Parse configuration
    config := &ScanConfig{
        JobID:      os.Getenv("SCAN_JOB_ID"),
        UserID:     os.Getenv("USER_ID"),
        Domains:    parseDomainsFromEnv(),
    }
    
    // 2. Initialize clients
    supabaseClient := NewSupabaseClient(
        os.Getenv("SUPABASE_URL"),
        os.Getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
    
    redisClient := redis.NewClient(&redis.Options{
        Addr: fmt.Sprintf("%s:%s", 
            os.Getenv("REDIS_HOST"), 
            os.Getenv("REDIS_PORT")),
    })
    
    // 3. Create scanner
    scanner := NewScanner(config, supabaseClient, redisClient)
    
    // 4. Execute scan
    results, err := scanner.ScanDomains(config.Domains)
    if err != nil {
        return fmt.Errorf("scan failed: %w", err)
    }
    
    // 5. Store results
    if err := supabaseClient.InsertSubdomains(results); err != nil {
        return fmt.Errorf("database insert failed: %w", err)
    }
    
    // 6. Stream results (if configured)
    if streamKey := os.Getenv("STREAM_OUTPUT_KEY"); streamKey != "" {
        if err := scanner.StreamResults(results, streamKey); err != nil {
            log.Printf("⚠️ Streaming failed (non-fatal): %v", err)
        }
    }
    
    log.Printf("✅ Processed %d domains, found %d results", 
        len(config.Domains), len(results))
    
    return nil
}
```

**For Consumers (DNSx pattern)**:

```go
// TEMPLATE PATTERN: Simple Mode (Consumer)
func runSimpleMode() error {
    // 1. Parse configuration
    config := &ScanConfig{
        JobID:      os.Getenv("SCAN_JOB_ID"),
        UserID:     os.Getenv("USER_ID"),
        Domains:    parseDomainsFromEnv(),  // Direct input, no streaming
    }
    
    // 2. Initialize clients
    supabaseClient := NewSupabaseClient(
        os.Getenv("SUPABASE_URL"),
        os.Getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
    
    // 3. Create scanner
    scanner := NewScanner(config, supabaseClient)
    
    // 4. Process each domain
    var allResults []DNSRecord
    for _, domain := range config.Domains {
        log.Printf("🔍 Resolving: %s", domain)
        
        records, _ := scanner.ResolveDNS(domain)
        allResults = append(allResults, records...)
    }
    
    // 5. Bulk insert results
    if err := supabaseClient.InsertDNSRecords(allResults); err != nil {
        return fmt.Errorf("database insert failed: %w", err)
    }
    
    log.Printf("✅ Resolved %d domains, stored %d records", 
        len(config.Domains), len(allResults))
    
    return nil
}
```

### 2.4: Batch Mode Implementation

**Database Fetch Pattern**:

```go
// TEMPLATE PATTERN: Batch Mode with Database Fetch
func runBatchMode() error {
    config := &BatchConfig{
        JobID:       os.Getenv("SCAN_JOB_ID"),
        BatchID:     os.Getenv("BATCH_ID"),
        AssetID:     os.Getenv("ASSET_ID"),
        Offset:      parseIntEnv("BATCH_OFFSET"),
        Limit:       parseIntEnv("BATCH_LIMIT"),
    }
    
    log.Printf("📦 Batch configuration: offset=%d, limit=%d", 
        config.Offset, config.Limit)
    
    // Initialize database
    supabaseClient := NewSupabaseClient(
        os.Getenv("SUPABASE_URL"),
        os.Getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
    
    // Fetch input data from database (consumer modules)
    // Example: DNSx fetches subdomains from Subfinder
    domains, err := supabaseClient.FetchSubdomains(
        config.AssetID, 
        config.Offset, 
        config.Limit,
    )
    if err != nil {
        return fmt.Errorf("failed to fetch domains: %w", err)
    }
    
    log.Printf("📊 Fetched %d domains from database", len(domains))
    
    // Process domains
    scanner := NewScanner(config, supabaseClient)
    results, err := scanner.ProcessBatch(domains)
    if err != nil {
        return fmt.Errorf("batch processing failed: %w", err)
    }
    
    // Update batch progress
    if err := supabaseClient.UpdateBatchProgress(
        config.BatchID, 
        len(results),
    ); err != nil {
        log.Printf("⚠️ Failed to update progress: %v", err)
    }
    
    log.Printf("✅ Batch completed: %d/%d processed", 
        len(results), len(domains))
    
    return nil
}
```

### 2.5: Streaming Mode (Consumer)

**Full Streaming Consumer** (DNSx pattern):

```go
// TEMPLATE PATTERN: Streaming Consumer
func runStreamingMode() error {
    config := &StreamingConfig{
        JobID:           os.Getenv("SCAN_JOB_ID"),
        StreamInputKey:  os.Getenv("STREAM_INPUT_KEY"),
        ConsumerGroup:   os.Getenv("CONSUMER_GROUP_NAME"),
        ConsumerName:    os.Getenv("CONSUMER_NAME"),
        BatchSize:       50,  // Messages per XREADGROUP
        BlockTime:       5 * time.Second,
        MaxProcessingTime: 1 * time.Hour,
    }
    
    log.Printf("📡 Streaming config: stream=%s, group=%s, consumer=%s", 
        config.StreamInputKey, config.ConsumerGroup, config.ConsumerName)
    
    // Initialize Redis
    redisClient := redis.NewClient(&redis.Options{
        Addr: fmt.Sprintf("%s:%s", 
            os.Getenv("REDIS_HOST"), 
            os.Getenv("REDIS_PORT")),
    })
    
    ctx := context.Background()
    
    // Create consumer group (idempotent)
    err := redisClient.XGroupCreateMkStream(ctx, 
        config.StreamInputKey, 
        config.ConsumerGroup, 
        "0",  // Start from beginning
    ).Err()
    
    if err != nil && !strings.Contains(err.Error(), "BUSYGROUP") {
        return fmt.Errorf("failed to create consumer group: %w", err)
    }
    
    log.Println("✅ Consumer group ready")
    
    // Initialize database
    supabaseClient := NewSupabaseClient(
        os.Getenv("SUPABASE_URL"),
        os.Getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
    
    // Initialize scanner
    scanner := NewScanner(config, supabaseClient)
    
    // Consumption loop
    startTime := time.Now()
    messagesProcessed := 0
    
    for {
        // Timeout check
        if time.Since(startTime) > config.MaxProcessingTime {
            log.Println("⏰ Max processing time reached")
            break
        }
        
        // Read messages (blocking)
        streams, err := redisClient.XReadGroup(ctx, &redis.XReadGroupArgs{
            Group:    config.ConsumerGroup,
            Consumer: config.ConsumerName,
            Streams:  []string{config.StreamInputKey, ">"},
            Count:    50,
            Block:    5 * time.Second,
        }).Result()
        
        if err == redis.Nil {
            // No new messages, continue blocking
            continue
        }
        
        for _, stream := range streams {
            for _, message := range stream.Messages {
                // Check for completion marker
                if msgType, ok := message.Values["type"].(string); ok && msgType == "completion" {
                    log.Println("Completion marker received")
                    redisClient.XAck(ctx, stream.Stream, config.ConsumerGroup, message.ID)
                    return nil
                }
                
                // Parse domain from message
                domain := parseSubdomainFromMessage(message.Values)
                
                // Process domain
                result, err := scanner.ProcessDomain(domain)
                if err != nil {
                    log.Printf("⚠️ Failed to process %s: %v", domain, err)
                } else {
                    // Store result
                    if err := supabaseClient.InsertDNSRecord(result); err != nil {
                        log.Printf("⚠️ Failed to store result: %v", err)
                    }
                }
                
                // Acknowledge message
                redisClient.XAck(ctx, stream.Stream, config.ConsumerGroup, message.ID)
                messagesProcessed++
                
                // Log progress every 50 messages
                if messagesProcessed%50 == 0 {
                    log.Printf("📊 Progress: %d messages processed", messagesProcessed)
                }
            }
        }
    }
    
    log.Printf("✅ Streaming completed: %d messages processed", messagesProcessed)
    return nil
}

// TEMPLATE PATTERN: Parse Message from Redis Stream
func parseSubdomainFromMessage(values map[string]interface{}) string {
    if subdomain, ok := values["subdomain"].(string); ok {
        return subdomain
    }
    log.Printf("⚠️ Invalid message format: %v", values)
    return ""
}
```

---

## Step 3: Database Integration

### 3.1: Supabase Client (`database.go`)

**Template Pattern**:

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

// TEMPLATE PATTERN: Supabase Client Structure
type SupabaseClient struct {
    URL        string
    ServiceKey string
    HTTPClient *http.Client
}

func NewSupabaseClient(url, serviceKey string) *SupabaseClient {
    return &SupabaseClient{
        URL:        url,
        ServiceKey: serviceKey,
        HTTPClient: &http.Client{
            Timeout: 30 * time.Second,
        },
    }
}

// TEMPLATE PATTERN: Insert Records
func (c *SupabaseClient) InsertSubdomains(records []SubdomainRecord) error {
    jsonData, err := json.Marshal(records)
    if err != nil {
        return fmt.Errorf("failed to marshal records: %w", err)
    }
    
    req, err := http.NewRequest("POST",
        fmt.Sprintf("%s/rest/v1/subdomains", c.URL),
        bytes.NewBuffer(jsonData))
    if err != nil {
        return fmt.Errorf("failed to create request: %w", err)
    }
    
    // TEMPLATE PATTERN: Supabase Headers
    req.Header.Set("apikey", c.ServiceKey)
    req.Header.Set("Authorization", "Bearer "+c.ServiceKey)
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Prefer", "return=minimal")  // Don't return inserted data
    
    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return fmt.Errorf("request failed: %w", err)
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusCreated && resp.StatusCode != http.StatusOK {
        return fmt.Errorf("insert failed with status: %d", resp.StatusCode)
    }
    
    return nil
}

// TEMPLATE PATTERN: Fetch Records (Consumer Modules)
func (c *SupabaseClient) FetchSubdomains(assetID string, offset, limit int) ([]string, error) {
    url := fmt.Sprintf("%s/rest/v1/subdomains?asset_id=eq.%s&order=discovered_at.desc&limit=%d&offset=%d",
        c.URL, assetID, limit, offset)
    
    req, err := http.NewRequest("GET", url, nil)
    if err != nil {
        return nil, fmt.Errorf("failed to create request: %w", err)
    }
    
    req.Header.Set("apikey", c.ServiceKey)
    req.Header.Set("Authorization", "Bearer "+c.ServiceKey)
    
    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return nil, fmt.Errorf("request failed: %w", err)
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusOK {
        return nil, fmt.Errorf("fetch failed with status: %d", resp.StatusCode)
    }
    
    var records []struct {
        Subdomain string `json:"subdomain"`
    }
    
    if err := json.NewDecoder(resp.Body).Decode(&records); err != nil {
        return nil, fmt.Errorf("failed to decode response: %w", err)
    }
    
    subdomains := make([]string, len(records))
    for i, r := range records {
        subdomains[i] = r.Subdomain
    }
    
    return subdomains, nil
}

// TEMPLATE PATTERN: Update Batch Progress
func (c *SupabaseClient) UpdateBatchProgress(batchID string, completedCount int) error {
    payload := map[string]interface{}{
        "completed_domains": completedCount,
    }
    
    jsonData, err := json.Marshal(payload)
    if err != nil {
        return fmt.Errorf("failed to marshal payload: %w", err)
    }
    
    url := fmt.Sprintf("%s/rest/v1/batch_scan_jobs?id=eq.%s", c.URL, batchID)
    
    req, err := http.NewRequest("PATCH", url, bytes.NewBuffer(jsonData))
    if err != nil {
        return fmt.Errorf("failed to create request: %w", err)
    }
    
    req.Header.Set("apikey", c.ServiceKey)
    req.Header.Set("Authorization", "Bearer "+c.ServiceKey)
    req.Header.Set("Content-Type", "application/json")
    
    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return fmt.Errorf("request failed: %w", err)
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
        return fmt.Errorf("update failed with status: %d", resp.StatusCode)
    }
    
    return nil
}
```

---

## Step 4: Redis Streaming (Optional)

### 4.1: Producer Pattern (Subfinder)

**Streaming Results** (`scanner.go`):

```go
// TEMPLATE PATTERN: Stream Producer
func (s *Scanner) StreamResults(results []SubdomainRecord, streamKey string) error {
    ctx := context.Background()
    
    for _, result := range results {
        // TEMPLATE PATTERN: XADD with Structured Data
        _, err := s.redisClient.XAdd(ctx, &redis.XAddArgs{
            Stream: streamKey,
            MaxLen: 10000,  // Prevent unbounded growth
            Approx: true,   // Use ~ for performance
            Values: map[string]interface{}{
                "subdomain":      result.Subdomain,
                "parent_domain":  result.ParentDomain,
                "source":         "subfinder",
                "discovered_at":  time.Now().UTC().Format(time.RFC3339Nano),
                "scan_job_id":    s.config.JobID,
                "asset_id":       s.config.AssetID,
            },
        }).Result()
        
        if err != nil {
            return fmt.Errorf("XADD failed: %w", err)
        }
    }
    
    // TEMPLATE PATTERN: Send Completion Marker
    return s.sendCompletionMarker(len(results))
}

// TEMPLATE PATTERN: Completion Marker
func (s *Scanner) sendCompletionMarker(totalResults int) error {
    ctx := context.Background()
    
    _, err := s.redisClient.XAdd(ctx, &redis.XAddArgs{
        Stream: s.config.StreamOutputKey,
        Values: map[string]interface{}{
            "type":          "completion",
            "module":        "subfinder",
            "scan_job_id":   s.config.JobID,
            "timestamp":     time.Now().UTC().Format(time.RFC3339),
            "total_results": totalResults,
        },
    }).Result()
    
    if err != nil {
        return fmt.Errorf("failed to send completion marker: %w", err)
    }
    
    log.Printf("📤 Sent completion marker: %d results", totalResults)
    return nil
}
```

---

## Step 5: ECS Task Definition

### 5.1: Terraform Configuration

**Module Task Definition** (`terraform/ecs_task_definitions.tf`):

```hcl
# Nuclei Scanner Task Definition
resource "aws_ecs_task_definition" "nuclei_scanner" {
  family                   = "neobotnet-v2-${var.environment}-nuclei"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"   # Default, overridden at runtime
  memory                   = "512"   # Default, overridden at runtime
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "nuclei-scanner"
      image     = "${aws_ecr_repository.nuclei_scanner.repository_url}:latest"
      essential = true

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/aws/ecs/neobotnet-v2-${var.environment}"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "nuclei"
        }
      }

      environment = []  # Injected at runtime via containerOverrides
    }
  ])

  tags = {
    Name        = "neobotnet-v2-${var.environment}-nuclei"
    Environment = var.environment
    Module      = "nuclei"
  }
}
```

### 5.2: Manual Creation (AWS Console)

**Steps**:

1. Navigate to **ECS → Task Definitions → Create new task definition**
2. Select **Fargate** launch type
3. Configure:
   - **Family**: `neobotnet-v2-dev-nuclei`
   - **CPU**: `256` (default, overridden at runtime)
   - **Memory**: `512` (default, overridden at runtime)
   - **Task Role**: `ecsTaskRole`
   - **Execution Role**: `ecsTaskExecutionRole`
4. Add Container:
   - **Name**: `nuclei-scanner`
   - **Image**: `123456789.dkr.ecr.us-east-1.amazonaws.com/neobotnet-v2-dev/nuclei:latest`
   - **Logging**: CloudWatch Logs
     - Log group: `/aws/ecs/neobotnet-v2-dev`
     - Stream prefix: `nuclei`
5. **Create**

---

## Step 6: Testing

### 6.1: Local Docker Test

```bash
# Build image
cd backend/containers/nuclei-go
docker build -t nuclei-go:local .

# Test simple mode
docker run --rm \
  -e SCAN_JOB_ID="test-$(uuidgen)" \
  -e USER_ID="de787f14-f5c3-41cf-967d-9ce528b9bd75" \
  -e DOMAINS='["example.com"]' \
  -e SUPABASE_URL="https://yourproject.supabase.co" \
  -e SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_KEY" \
  nuclei-go:local
```

**Expected Output**:
```
🚀 Nuclei Scanner starting...
📋 Execution mode: SIMPLE
✅ Environment validation passed
🔍 Scanning: example.com
✅ Processed 1 domains, found 5 findings
✅ Nuclei scan completed successfully
```

### 6.2: Integration Test (API)

```bash
# Create scan via API
curl -X POST https://aldous-api.neobotnet.com/api/v1/scans \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_ids": ["6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e"],
    "modules": ["subfinder", "dnsx", "httpx", "nuclei"],
    "active_domains_only": true
  }'

# Response:
# {"scan_id": "3f8e1a2b-4c5d-6e7f-8a9b-0c1d2e3f4a5b", "status": "pending"}

# Monitor status
watch -n 5 'curl -s https://aldous-api.neobotnet.com/api/v1/scans/3f8e1a2b \
  -H "Authorization: Bearer $TOKEN" | jq ".status"'
```

### 6.3: Verify Results

```sql
-- Check scan completion
SELECT status, completed_at FROM scans WHERE id = '3f8e1a2b';

-- Verify module executed
SELECT module, status FROM asset_scan_jobs WHERE scan_id = '3f8e1a2b';

-- Check results count
SELECT COUNT(*) FROM nuclei_findings WHERE scan_job_id = '3f8e1a2b';
```

---

## Step 7: Deployment

### 7.1: Build and Push to ECR

```bash
# Authenticate with ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.us-east-1.amazonaws.com

# Build for production
cd backend/containers/nuclei-go
docker build -t neobotnet-v2-dev/nuclei:latest .

# Tag image
docker tag neobotnet-v2-dev/nuclei:latest \
  123456789.dkr.ecr.us-east-1.amazonaws.com/neobotnet-v2-dev/nuclei:latest

# Push to ECR
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/neobotnet-v2-dev/nuclei:latest
```

### 7.2: Register Task Definition

**If using Terraform**:
```bash
cd terraform
terraform apply
```

**If using AWS CLI**:
```bash
# Register new task definition revision
aws ecs register-task-definition \
  --cli-input-json file://nuclei-task-definition.json
```

### 7.3: Verify Deployment

```bash
# Verify image in ECR
aws ecr describe-images \
  --repository-name neobotnet-v2-dev/nuclei \
  --region us-east-1

# Verify task definition
aws ecs describe-task-definition \
  --task-definition neobotnet-v2-dev-nuclei

# Test via API (from step 6.2)
```

---

## Reference Implementations

### Subfinder (Producer)

**Key Files**:
- `backend/containers/subfinder-go/main.go` - Mode routing
- `backend/containers/subfinder-go/scanner.go` - Scanning + streaming
- `backend/containers/subfinder-go/database.go` - Supabase integration

**Characteristics**:
- ✅ Producer pattern (streams subdomains)
- ✅ No dependencies
- ✅ Supports batching
- ✅ Simple + Batch + Streaming modes

**Code Snippet** (`scanner.go:45-70`):
```go
// TEMPLATE PATTERN: Producer Streaming
func (s *Scanner) streamSubdomainsToRedis(result *DomainScanResult) error {
    ctx := context.Background()
    
    for _, subdomain := range result.Subdomains {
        _, err := s.redisClient.XAdd(ctx, &redis.XAddArgs{
            Stream: s.config.StreamOutputKey,
            MaxLen: 10000,
            Approx: true,
            Values: map[string]interface{}{
                "subdomain":      subdomain,
                "parent_domain":  result.Domain,
                "source":         "subfinder",
                "discovered_at":  time.Now().UTC().Format(time.RFC3339Nano),
                "scan_job_id":    s.config.JobID,
                "asset_id":       s.config.AssetID,
            },
        }).Result()
        
        if err != nil {
            return fmt.Errorf("XADD failed: %w", err)
        }
    }
    
    return s.sendCompletionMarker(len(result.Subdomains))
}
```

### DNSx (Consumer)

**Key Files**:
- `backend/containers/dnsx-go/main.go` - Mode routing
- `backend/containers/dnsx-go/streaming.go` - Redis consumer
- `backend/containers/dnsx-go/batch_support.go` - Batch database fetch

**Characteristics**:
- ✅ Consumer pattern (reads from Subfinder stream)
- ✅ Dependency: `[subfinder]`
- ✅ Supports batching
- ✅ All three modes

**Code Snippet** (`streaming.go:120-150`):
```go
// TEMPLATE PATTERN: Consumer Streaming
for {
    streams, err := redisClient.XReadGroup(ctx, &redis.XReadGroupArgs{
        Group:    config.ConsumerGroup,
        Consumer: config.ConsumerName,
        Streams:  []string{config.StreamInputKey, ">"},
        Count:    50,
        Block:    5 * time.Second,
    }).Result()
    
    if err == redis.Nil {
        continue
    }
    
    for _, stream := range streams {
        for _, message := range stream.Messages {
            // Check for completion
            if msgType, ok := message.Values["type"].(string); ok && msgType == "completion" {
                log.Println("Completion marker received")
                redisClient.XAck(ctx, stream.Stream, config.ConsumerGroup, message.ID)
                return nil
            }
            
            // Process subdomain
            subdomain := message.Values["subdomain"].(string)
            records, _ := resolveDNS(subdomain)
            supabaseClient.InsertDNSRecords(records)
            
            // Acknowledge
            redisClient.XAck(ctx, stream.Stream, config.ConsumerGroup, message.ID)
        }
    }
}
```

### HTTPx (Consumer)

**Key Files**:
- `backend/containers/httpx-go/main.go` - Mode routing
- `backend/containers/httpx-go/scanner.go` - HTTP probing

**Characteristics**:
- ✅ Consumer pattern (reads from DNSx stream)
- ✅ Dependency: `[dnsx]` (transitively depends on `[subfinder]`)
- ✅ Supports batching
- ✅ HTTP probing with screenshots

**Use Case**: HTTP probing, technology detection, screenshot capture

---

**Document Version**: 1.0  
**Last Updated**: November 19, 2025  
**Previous**: [← Module System Deep Dive](02-MODULE-SYSTEM.md) | **Next**: [Configuration Reference →](04-MODULE-CONFIGURATION-REFERENCE.md)
