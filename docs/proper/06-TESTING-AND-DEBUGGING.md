# Testing & Debugging Guide

**Development, Troubleshooting, and Performance Analysis**

---

## Table of Contents

1. [Local Development Testing](#local-development-testing)
2. [CloudWatch Log Analysis](#cloudwatch-log-analysis)
3. [Redis Debugging](#redis-debugging)
4. [Common Error Scenarios](#common-error-scenarios)
5. [Performance Profiling](#performance-profiling)
6. [Integration Testing](#integration-testing)
7. [Debugging Workflows](#debugging-workflows)

---

## Local Development Testing

### Environment Setup

**VPC Limitations**: ECS tasks run in private subnets and **cannot** be tested locally without VPN/bastion access.

**Testing Strategies**:

1. **Local Container Execution** (Docker Compose)
2. **Backend Unit Tests** (Pytest)
3. **VPS Staging Environment** (http://172.236.127.72:8000)
4. **Cloud Staging Environment** (https://aldous-api.neobotnet.com)

### Strategy 1: Local Docker Testing

**Module Container** (`backend/containers/subfinder-go`):

```bash
# Build image
cd backend/containers/subfinder-go
docker build -t subfinder-go:local .

# Run with test environment
docker run --rm \
  -e DOMAINS='["example.com"]' \
  -e SCAN_JOB_ID="test-$(uuidgen)" \
  -e USER_ID="de787f14-f5c3-41cf-967d-9ce528b9bd75" \
  -e SUPABASE_URL="https://yourproject.supabase.co" \
  -e SUPABASE_SERVICE_ROLE_KEY="eyJhbGc..." \
  subfinder-go:local
```

**Expected Output**:
```
2025-11-19T12:34:56Z INFO Starting Subfinder scanner
2025-11-19T12:34:56Z INFO Processing domain: example.com
2025-11-19T12:35:10Z INFO Found 42 subdomains
2025-11-19T12:35:11Z INFO Scan completed successfully
```

**With Redis (docker-compose)**:

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  subfinder:
    build: ./backend/containers/subfinder-go
    environment:
      DOMAINS: '["example.com"]'
      SCAN_JOB_ID: "test-scan-001"
      USER_ID: "de787f14-f5c3-41cf-967d-9ce528b9bd75"
      SUPABASE_URL: "https://yourproject.supabase.co"
      SUPABASE_SERVICE_ROLE_KEY: "${SUPABASE_KEY}"
      STREAMING_MODE: "true"
      STREAM_OUTPUT_KEY: "scan:test-scan-001:subfinder:output"
      REDIS_HOST: "redis"
      REDIS_PORT: "6379"
    depends_on:
      - redis
```

**Run Test**:
```bash
export SUPABASE_KEY="eyJhbGc..."
docker-compose -f docker-compose.test.yml up
```

### Strategy 2: Backend Unit Tests

**Pytest Configuration** (`backend/tests/conftest.py`):

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_supabase():
    """Mock Supabase client"""
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{
            'module_name': 'subfinder',
            'supports_batching': True,
            'max_batch_size': 200,
            'dependencies': []
        }]
    )
    return client

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.xadd = AsyncMock(return_value="1234567890-0")
    return redis

@pytest.fixture
def mock_ecs_client():
    """Mock ECS client"""
    client = MagicMock()
    client.run_task.return_value = {
        'tasks': [{
            'taskArn': 'arn:aws:ecs:us-east-1:123456789:task/abc'
        }]
    }
    return client
```

**Test ModuleRegistry** (`backend/tests/services/test_module_registry.py`):

```python
import pytest
from app.services.module_registry import ModuleRegistry

@pytest.mark.asyncio
async def test_module_discovery(mock_supabase):
    """Test module discovery from database"""
    registry = ModuleRegistry()
    
    # Initialize with mock
    await registry.initialize(mock_supabase)
    
    # Verify module loaded
    modules = await registry.list_modules()
    assert 'subfinder' in modules
    assert len(modules) > 0

@pytest.mark.asyncio
async def test_dependency_resolution():
    """Test dependency auto-configuration"""
    registry = ModuleRegistry()
    
    # Module with dependencies should auto-enable database fetch
    module = await registry.get_module('dnsx')
    assert module.optimization_hints.get('requires_database_fetch') == True
    assert module.dependencies == ['subfinder']

@pytest.mark.asyncio
async def test_circular_dependency_detection():
    """Test circular dependency detection"""
    registry = ModuleRegistry()
    
    with pytest.raises(ValueError, match="Circular dependency"):
        await registry.validate_dependencies(['moduleA', 'moduleB'])
```

**Run Tests**:
```bash
cd backend

# Run all tests
pytest

# Run specific test file
pytest tests/services/test_module_registry.py

# Run with coverage
pytest --cov=app --cov-report=html
```

### Strategy 3: API Integration Testing

**Test Scan Creation** (`backend/tests/api/test_scans.py`):

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_scan(client: AsyncClient, auth_headers):
    """Test scan creation endpoint"""
    payload = {
        "asset_ids": ["6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e"],
        "modules": ["subfinder"],
        "active_domains_only": True
    }
    
    response = await client.post("/api/v1/scans", json=payload, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "scan_id" in data
    assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_scan_validation_missing_asset(client: AsyncClient, auth_headers):
    """Test validation fails for non-existent asset"""
    payload = {
        "asset_ids": ["00000000-0000-0000-0000-000000000000"],
        "modules": ["subfinder"]
    }
    
    response = await client.post("/api/v1/scans", json=payload, headers=auth_headers)
    
    assert response.status_code == 404
    assert "Asset not found" in response.json()["detail"]
```

---

## CloudWatch Log Analysis

### Accessing Logs

**AWS Console**:
1. Navigate to CloudWatch → Log Groups
2. Select `/aws/ecs/neobotnet-v2-dev`
3. Filter by log stream: `subfinder/{task_id}`

**AWS CLI**:
```bash
# Get recent logs for module
aws logs tail /aws/ecs/neobotnet-v2-dev \
  --follow \
  --filter-pattern "subfinder" \
  --since 10m

# Get logs for specific task
aws logs get-log-events \
  --log-group-name /aws/ecs/neobotnet-v2-dev \
  --log-stream-name subfinder/subfinder-scanner/abc123def456 \
  --limit 100
```

### Log Format

**Standard Module Logs**:
```
2025-11-19T12:34:56.789Z [INFO] scan_job_id=3f8e1a2b Starting Subfinder scan
2025-11-19T12:34:57.123Z [INFO] scan_job_id=3f8e1a2b domain=example.com sources=15
2025-11-19T12:35:10.456Z [INFO] scan_job_id=3f8e1a2b subdomain=api.example.com discovered
2025-11-19T12:35:11.789Z [INFO] scan_job_id=3f8e1a2b Scan completed: 42 subdomains
```

**Key Fields**:
- **Timestamp**: ISO8601 format, UTC timezone
- **Level**: `INFO`, `WARN`, `ERROR`
- **scan_job_id**: Correlation ID for tracing
- **Message**: Human-readable event

### Correlation ID Tracing

**Follow scan across modules**:

```bash
# Search all logs for specific scan
aws logs filter-log-events \
  --log-group-name /aws/ecs/neobotnet-v2-dev \
  --filter-pattern "3f8e1a2b" \
  --start-time $(date -d '1 hour ago' +%s)000

# Output shows full pipeline:
# [Subfinder] scan_job_id=3f8e1a2b Starting scan
# [Subfinder] scan_job_id=3f8e1a2b Found 42 subdomains
# [DNSx] scan_job_id=3f8e1a2b Consuming stream
# [DNSx] scan_job_id=3f8e1a2b Resolved 42 DNS records
# [HTTPx] scan_job_id=3f8e1a2b Probing 42 URLs
```

### Error Log Patterns

**Module Crash** (Exit Code != 0):
```
2025-11-19T12:35:00Z [ERROR] scan_job_id=3f8e1a2b Failed to connect to Supabase: connection timeout
2025-11-19T12:35:00Z [ERROR] scan_job_id=3f8e1a2b Stack trace:
  at supabase.go:42
  at main.go:18
2025-11-19T12:35:01Z [INFO] ECS Task stopped with exit code: 1
```

**Redis Connection Failure**:
```
2025-11-19T12:35:00Z [ERROR] scan_job_id=3f8e1a2b Redis XADD failed: dial tcp 10.0.1.5:6379: i/o timeout
2025-11-19T12:35:00Z [WARN] scan_job_id=3f8e1a2b Retrying connection (attempt 2/3)
```

**Database Timeout**:
```
2025-11-19T12:35:15Z [ERROR] scan_job_id=3f8e1a2b Database query timeout after 30s
2025-11-19T12:35:15Z [ERROR] scan_job_id=3f8e1a2b Query: SELECT subdomain FROM subdomains WHERE...
```

### CloudWatch Insights Queries

**Query 1: Module Execution Times**:
```sql
fields @timestamp, scan_job_id, @message
| filter @message like /Scan completed/
| parse @message /duration=(?<duration>\d+)/
| stats avg(duration) as avg_duration by module
```

**Query 2: Error Rate**:
```sql
fields @timestamp, @message
| filter @logStream like /subfinder/
| filter level = "ERROR"
| stats count() as error_count by bin(5m)
```

**Query 3: Top Error Messages**:
```sql
fields @message
| filter level = "ERROR"
| stats count() as occurrences by @message
| sort occurrences desc
| limit 10
```

---

## Redis Debugging

### Redis CLI Access

**Connect to Redis**:
```bash
# Production (ElastiCache - requires VPN or bastion)
redis-cli -h cache.amazonaws.com -p 6379

# Local (docker-compose)
redis-cli -h localhost -p 6379
```

### Inspect Streams

**List Active Streams**:
```bash
# Find all scan streams
KEYS scan:*:output

# Output:
# 1) "scan:3f8e1a2b:subfinder:output"
# 2) "scan:3f8e1a2b:dnsx:output"
```

**Stream Info**:
```bash
XINFO STREAM scan:3f8e1a2b:subfinder:output

# Output:
# length: 247                    # Total messages
# radix-tree-keys: 1
# radix-tree-nodes: 2
# last-generated-id: 1700400000000-0
# groups: 1                      # Consumer groups
# first-entry: ...
# last-entry: ...
```

**Read Stream Messages**:
```bash
# Read last 10 messages
XREVRANGE scan:3f8e1a2b:subfinder:output + - COUNT 10

# Output:
# 1) 1) "1700400000000-0"
#    2) 1) "subdomain"
#       2) "api.example.com"
#       3) "parent_domain"
#       4) "example.com"
```

### Consumer Group Debugging

**List Consumer Groups**:
```bash
XINFO GROUPS scan:3f8e1a2b:subfinder:output

# Output:
# 1) 1) "name"
#    2) "dnsx-consumers"
#    3) "consumers"
#    4) 3                        # 3 active consumers
#    5) "pending"
#    6) 0                        # No pending messages (good!)
```

**Check Pending Messages**:
```bash
XPENDING scan:3f8e1a2b:subfinder:output dnsx-consumers

# Output:
# 1) 0                           # No pending (healthy)
# 2) (nil)
# 3) (nil)
# 4) (nil)

# OR (unhealthy):
# 1) 150                         # 150 pending messages!
# 2) "1700400000000-0"           # Oldest pending
# 3) "1700400500000-0"           # Newest pending
# 4) 1) 1) "dnsx-task-abc123"
#       2) "150"                 # Consumer stuck with 150 pending
```

**Claim Stuck Messages**:
```bash
# Force claim messages idle > 5 minutes
XCLAIM scan:3f8e1a2b:subfinder:output \
  dnsx-consumers \
  dnsx-task-xyz \
  300000 \
  1700400000000-0 1700400000001-0

# Reprocess claimed messages in your consumer
```

### Monitor Stream Growth

**Watch Stream Length**:
```bash
# Shell script to monitor stream
watch -n 5 'redis-cli XLEN scan:3f8e1a2b:subfinder:output'

# Output updates every 5 seconds:
# (integer) 100
# (integer) 247
# (integer) 430
```

**Trim Large Streams**:
```bash
# Prevent memory issues by trimming
XTRIM scan:3f8e1a2b:subfinder:output MAXLEN ~ 10000

# ~ means approximate (faster, recommended)
```

### Redis Pub/Sub Debugging

**Subscribe to WebSocket Updates**:
```bash
SUBSCRIBE scan:3f8e1a2b:updates

# Output (real-time):
# 1) "message"
# 2) "scan:3f8e1a2b:updates"
# 3) "{\"type\":\"progress\",\"subdomains_found\":42}"
```

---

## Common Error Scenarios

### Scenario 1: "Module Not Found"

**Symptom**:
```json
{
  "error": "ModuleNotFound",
  "message": "Module 'subfindeer' not found"
}
```

**Cause**: Typo in module name or module not inserted into `scan_module_profiles`

**Solution**:
```sql
-- Check available modules
SELECT module_name, is_active FROM scan_module_profiles;

-- Verify spelling (common typos)
-- ❌ subfindeer
-- ❌ sub-finder
-- ✅ subfinder

-- If missing, insert module profile
INSERT INTO scan_module_profiles (...) VALUES (...);
```

### Scenario 2: "Circular Dependency"

**Symptom**:
```json
{
  "error": "CircularDependency",
  "message": "Circular dependency detected: moduleA → moduleB → moduleA"
}
```

**Cause**: Invalid dependency configuration

**Solution**:
```sql
-- Check dependencies
SELECT module_name, dependencies FROM scan_module_profiles;

-- Fix circular reference
-- ❌ moduleA depends on [moduleB], moduleB depends on [moduleA]
-- ✅ moduleA depends on [], moduleB depends on [moduleA]

UPDATE scan_module_profiles
SET dependencies = ARRAY['moduleA']
WHERE module_name = 'moduleB';
```

### Scenario 3: "Task Failed to Start"

**Symptom**:
CloudWatch shows:
```
Task stopped at: 2025-11-19T12:35:00Z
Stop reason: TaskFailedToStart
Stop code: CannotPullContainerError
```

**Cause**: ECR image doesn't exist or permissions issue

**Solution**:
```bash
# Verify image exists
aws ecr describe-images \
  --repository-name neobotnet-v2-dev/subfinder \
  --region us-east-1

# Check ECR permissions
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.us-east-1.amazonaws.com

# Rebuild and push image
docker build -t 123456789.dkr.ecr.us-east-1.amazonaws.com/neobotnet-v2-dev/subfinder:latest .
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/neobotnet-v2-dev/subfinder:latest
```

### Scenario 4: "Consumer Not Consuming"

**Symptom**:
- Subfinder completes
- Stream has 247 messages
- DNSx task running but no progress

**Diagnosis**:
```bash
# Check stream has messages
redis-cli XLEN scan:3f8e1a2b:subfinder:output
# (integer) 247

# Check consumer group exists
redis-cli XINFO GROUPS scan:3f8e1a2b:subfinder:output
# (empty array) ← Problem: No consumer group!
```

**Solution**:
```go
// DNSx must create consumer group before reading
err := redisClient.XGroupCreateMkStream(ctx,
    "scan:3f8e1a2b:subfinder:output",
    "dnsx-consumers",
    "0"  // Read from beginning
).Err()
```

### Scenario 5: "Database Connection Timeout"

**Symptom**:
CloudWatch logs:
```
2025-11-19T12:35:15Z [ERROR] Database connection timeout after 30s
```

**Cause**: Supabase connection pool exhausted or network issue

**Solution**:

1. **Check Supabase Dashboard**: Project → Settings → Database → Connection pooling
2. **Increase timeout**:
   ```go
   db, err := sql.Open("postgres", fmt.Sprintf(
       "%s?connect_timeout=60",  // Increase from 30s to 60s
       connectionString,
   ))
   ```
3. **Use connection pooling**:
   ```go
   db.SetMaxOpenConns(25)    // Limit concurrent connections
   db.SetMaxIdleConns(5)     // Reuse connections
   db.SetConnMaxLifetime(5 * time.Minute)
   ```

---

## Performance Profiling

### Module Execution Time

**Log Duration** (`backend/containers/subfinder-go/scanner.go`):

```go
func (s *Scanner) Run() error {
    startTime := time.Now()
    defer func() {
        duration := time.Since(startTime)
        log.Printf("[METRIC] scan_duration_seconds=%d domains=%d",
            int(duration.Seconds()),
            len(s.config.Domains))
    }()
    
    // ... scan logic
}
```

**CloudWatch Insights Query**:
```sql
fields scan_duration_seconds, domains
| filter @message like /METRIC/
| stats avg(scan_duration_seconds) as avg_duration,
        avg(domains) as avg_domains
| extend avg_seconds_per_domain = avg_duration / avg_domains
```

### Database Query Performance

**Log Slow Queries**:

```go
func (c *SupabaseClient) InsertSubdomains(subdomains []Subdomain) error {
    start := time.Now()
    
    // Execute query
    result, err := c.db.Exec(query, args...)
    
    duration := time.Since(start)
    if duration > 5*time.Second {
        log.Warnf("[SLOW_QUERY] duration=%dms query=%s",
            duration.Milliseconds(),
            query)
    }
    
    return err
}
```

**Supabase Dashboard**: Project → Database → Query Performance (shows slow queries)

### Redis Latency Monitoring

**Enable Redis Latency Monitoring**:
```bash
redis-cli CONFIG SET latency-monitor-threshold 100  # Log commands > 100ms

# View latency events
redis-cli LATENCY LATEST

# Output:
# 1) 1) "command"
#    2) (integer) 1700400000  # Timestamp
#    3) (integer) 150         # Latency (ms)
#    4) (integer) 200         # Max latency
```

### Go Profiling (pprof)

**Enable HTTP pprof Server** (`main.go`):

```go
import (
    "net/http"
    _ "net/http/pprof"
)

func main() {
    // Start pprof server
    go func() {
        log.Println(http.ListenAndServe("localhost:6060", nil))
    }()
    
    // ... normal module logic
}
```

**Collect CPU Profile** (requires SSH/bastion to ECS task):
```bash
# Capture 30-second CPU profile
curl http://localhost:6060/debug/pprof/profile?seconds=30 > cpu.prof

# Analyze with go tool
go tool pprof cpu.prof

# Interactive commands:
# (pprof) top10        # Top 10 CPU consumers
# (pprof) list main.scanDomain  # Show source code
# (pprof) web          # Generate graph (requires graphviz)
```

---

## Integration Testing

### End-to-End Scan Test

**Test Script** (`scripts/test_scan_e2e.sh`):

```bash
#!/bin/bash
set -e

API_URL="https://aldous-api.neobotnet.com"
AUTH_TOKEN="eyJhbGc..."  # Get from login

echo "=== Creating Scan ==="
RESPONSE=$(curl -s -X POST "$API_URL/api/v1/scans" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_ids": ["6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e"],
    "modules": ["subfinder", "dnsx"],
    "active_domains_only": true
  }')

SCAN_ID=$(echo $RESPONSE | jq -r '.scan_id')
echo "Scan ID: $SCAN_ID"

echo "=== Polling Status ==="
for i in {1..60}; do
  STATUS=$(curl -s "$API_URL/api/v1/scans/$SCAN_ID" \
    -H "Authorization: Bearer $AUTH_TOKEN" | jq -r '.status')
  
  echo "[$i/60] Status: $STATUS"
  
  if [ "$STATUS" == "completed" ]; then
    echo "✅ Scan completed successfully"
    exit 0
  elif [ "$STATUS" == "failed" ]; then
    echo "❌ Scan failed"
    exit 1
  fi
  
  sleep 10
done

echo "❌ Timeout: Scan did not complete in 10 minutes"
exit 1
```

**Run Test**:
```bash
chmod +x scripts/test_scan_e2e.sh
./scripts/test_scan_e2e.sh
```

### Module Compatibility Matrix

**Test All Module Combinations**:

| Modules | Expected Result | Pass/Fail |
|---------|-----------------|-----------|
| `[subfinder]` | Subdomains stored | ✅ |
| `[subfinder, dnsx]` | DNS records stored | ✅ |
| `[subfinder, dnsx, httpx]` | HTTP probes stored | ✅ |
| `[dnsx]` (missing subfinder) | ❌ Validation error | ✅ |
| `[httpx]` (missing dnsx) | ❌ Validation error | ✅ |
| `[subfinder, httpx]` | ✅ Auto-includes dnsx | ✅ |

---

## Debugging Workflows

### Workflow 1: Module Not Producing Results

**Steps**:

1. **Verify ECS task started**:
   ```bash
   aws ecs list-tasks --cluster neobotnet-v2-dev-cluster
   ```

2. **Check CloudWatch logs**:
   ```bash
   aws logs tail /aws/ecs/neobotnet-v2-dev --follow --filter-pattern "scan_job_id=3f8e1a2b"
   ```

3. **Check database writes**:
   ```sql
   SELECT COUNT(*) FROM subdomains WHERE scan_job_id = '3f8e1a2b';
   ```

4. **Check Redis stream**:
   ```bash
   redis-cli XLEN scan:3f8e1a2b:subfinder:output
   ```

### Workflow 2: Consumer Not Processing Stream

**Steps**:

1. **Verify stream exists and has messages**:
   ```bash
   redis-cli XLEN scan:3f8e1a2b:subfinder:output
   # (integer) 247
   ```

2. **Check consumer group created**:
   ```bash
   redis-cli XINFO GROUPS scan:3f8e1a2b:subfinder:output
   ```

3. **Check pending messages**:
   ```bash
   redis-cli XPENDING scan:3f8e1a2b:subfinder:output dnsx-consumers
   ```

4. **Check consumer logs for errors**:
   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/ecs/neobotnet-v2-dev \
     --filter-pattern "dnsx scan_job_id=3f8e1a2b ERROR"
   ```

### Workflow 3: Scan Stuck in "Running" Status

**Steps**:

1. **Check ECS task status**:
   ```bash
   aws ecs describe-tasks \
     --cluster neobotnet-v2-dev-cluster \
     --tasks <task_arn>
   ```

2. **Check if task stopped unexpectedly**:
   ```bash
   # Look for "STOPPED" status with exit code
   ```

3. **Check batch_scan_jobs progress**:
   ```sql
   SELECT status, completed_domains, total_domains, error_message
   FROM batch_scan_jobs
   WHERE id = '<batch_id>';
   ```

4. **Manual status update** (if task failed but DB not updated):
   ```sql
   UPDATE scans SET status = 'failed', error_message = 'Task timeout'
   WHERE id = '3f8e1a2b';
   ```

---

**Document Version**: 1.0  
**Last Updated**: November 19, 2025  
**Previous**: [← Data Flow & Streaming](05-DATA-FLOW-AND-STREAMING.md) | **Index**: [Documentation Home](README.md)
