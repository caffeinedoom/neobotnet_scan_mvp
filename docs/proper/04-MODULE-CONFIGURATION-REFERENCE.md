# Module Configuration Reference

**Complete Configuration API and Specifications**

---

## Table of Contents

1. [Database Schema Reference](#database-schema-reference)
2. [Environment Variables](#environment-variables)
3. [Resource Scaling DSL](#resource-scaling-dsl)
4. [Optimization Hints](#optimization-hints)
5. [ECS Task Configuration](#ecs-task-configuration)
6. [Redis Conventions](#redis-conventions)
7. [Error Codes & Status Values](#error-codes--status-values)
8. [Configuration Examples](#configuration-examples)

---

## Database Schema Reference

### `scan_module_profiles` (Primary Module Configuration)

**Purpose**: Template definition for scan modules - single source of truth

**Schema**:
```sql
CREATE TABLE scan_module_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identity
    module_name TEXT NOT NULL UNIQUE,
    version TEXT DEFAULT '1.0' NOT NULL,
    
    -- Batching Capabilities
    supports_batching BOOLEAN DEFAULT false NOT NULL,
    max_batch_size INTEGER DEFAULT 1 NOT NULL 
        CHECK (max_batch_size >= 1),
    
    -- Resource Allocation
    resource_scaling JSONB NOT NULL,
    estimated_duration_per_domain INTEGER DEFAULT 120 NOT NULL 
        CHECK (estimated_duration_per_domain > 0),
    
    -- ECS Integration
    task_definition_template TEXT NOT NULL,
    container_name TEXT NOT NULL,
    
    -- Dependency Management
    dependencies TEXT[] DEFAULT '{}' NOT NULL,
    
    -- Module Configuration
    optimization_hints JSONB DEFAULT '{}',
    
    -- Lifecycle
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
```

**Field Reference**:

| Field | Type | Required | Default | Description | Example |
|-------|------|----------|---------|-------------|---------|
| `id` | UUID | ✅ | `gen_random_uuid()` | Unique identifier | Auto-generated |
| `module_name` | TEXT | ✅ | - | Unique module identifier | `"subfinder"`, `"dnsx"` |
| `version` | TEXT | ✅ | `"1.0"` | Semantic version | `"1.0"`, `"2.3.1"` |
| `supports_batching` | BOOLEAN | ✅ | `false` | Can process multiple domains in one task | `true` |
| `max_batch_size` | INTEGER | ✅ | `1` | Maximum domains per batch (1 = no batching) | `200` |
| `resource_scaling` | JSONB | ✅ | - | CPU/memory scaling configuration | See [Resource Scaling DSL](#resource-scaling-dsl) |
| `estimated_duration_per_domain` | INTEGER | ✅ | `120` | Seconds per domain (for timeout calc) | `60`, `300` |
| `task_definition_template` | TEXT | ✅ | - | ECS task definition family name or ARN | `"neobotnet-v2-dev-subfinder"` |
| `container_name` | TEXT | ✅ | - | Container name within task definition | `"subfinder-scanner"` |
| `dependencies` | TEXT[] | ✅ | `'{}'` | Array of module names that must execute first | `'{subfinder}'` |
| `optimization_hints` | JSONB | ⚠️ | `'{}'` | Module-specific configuration flags | See [Optimization Hints](#optimization-hints) |
| `is_active` | BOOLEAN | ✅ | `true` | Module available for discovery | `true`, `false` |

**Constraints**:
- `valid_duration`: `estimated_duration_per_domain > 0`
- `valid_max_batch_size`: `max_batch_size >= 1`
- `module_name` must be unique
- `version` follows semantic versioning (recommended, not enforced)

**Indexes**:
```sql
-- Primary key index (automatic)
CREATE UNIQUE INDEX scan_module_profiles_pkey ON scan_module_profiles(id);

-- Module name lookup (automatic via UNIQUE constraint)
CREATE UNIQUE INDEX scan_module_profiles_module_name_key ON scan_module_profiles(module_name);

-- Active module filtering
CREATE INDEX idx_scan_module_profiles_active ON scan_module_profiles(is_active) 
    WHERE is_active = true;
```

---

### `batch_scan_jobs` (Batch Execution Tracking)

**Purpose**: Track batch scan job execution and progress

**Schema**:
```sql
CREATE TABLE batch_scan_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Batch Configuration
    batch_type TEXT DEFAULT 'multi_asset' NOT NULL,
    module TEXT NOT NULL,
    status TEXT DEFAULT 'pending' NOT NULL,
    
    -- Domain Tracking
    total_domains INTEGER DEFAULT 0 NOT NULL,
    completed_domains INTEGER DEFAULT 0 NOT NULL,
    failed_domains INTEGER DEFAULT 0 NOT NULL,
    batch_domains TEXT[] DEFAULT '{}' NOT NULL,
    asset_scan_mapping JSONB DEFAULT '{}' NOT NULL,
    
    -- Resource Allocation
    allocated_cpu INTEGER DEFAULT 256 NOT NULL,
    allocated_memory INTEGER DEFAULT 512 NOT NULL,
    estimated_duration_minutes INTEGER DEFAULT 5 NOT NULL,
    resource_profile JSONB DEFAULT '{}',
    
    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    estimated_completion TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Error Handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    max_retries INTEGER DEFAULT 2 NOT NULL,
    
    -- ECS Integration
    ecs_task_arn TEXT,
    
    -- Additional Metadata
    metadata JSONB DEFAULT '{}',
    total_records INTEGER DEFAULT 0 NOT NULL,
    
    CONSTRAINT valid_batch_type CHECK (batch_type IN ('multi_asset', 'single_asset')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT valid_domain_counts CHECK (
        total_domains >= 0 AND 
        completed_domains >= 0 AND 
        failed_domains >= 0 AND 
        (completed_domains + failed_domains) <= total_domains
    ),
    CONSTRAINT valid_resources CHECK (
        allocated_cpu BETWEEN 256 AND 4096 AND
        allocated_memory BETWEEN 512 AND 8192
    ),
    CONSTRAINT valid_retry_count CHECK (retry_count >= 0 AND retry_count <= max_retries)
);
```

**Field Reference**:

| Field | Type | Description | Values |
|-------|------|-------------|--------|
| `batch_type` | TEXT | Batch grouping strategy | `"multi_asset"`, `"single_asset"` |
| `module` | TEXT | Module executing the batch | `"subfinder"`, `"dnsx"` |
| `status` | TEXT | Current batch status | `"pending"`, `"running"`, `"completed"`, `"failed"`, `"cancelled"` |
| `batch_domains` | TEXT[] | Array of domains in this batch | `['example.com', 'test.com']` |
| `asset_scan_mapping` | JSONB | Maps domains to asset_scan_ids | `{"example.com": "uuid"}` |
| `allocated_cpu` | INTEGER | CPU units allocated (ECS) | `256` - `4096` |
| `allocated_memory` | INTEGER | Memory in MB (ECS) | `512` - `8192` |
| `ecs_task_arn` | TEXT | ECS task ARN when running | `"arn:aws:ecs:..."` |

---

## Environment Variables

### Required Variables (All Modes)

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `SCAN_JOB_ID` | UUID | Scan job identifier for tracking | `"3f8e1a2b-4c5d-6e7f-8a9b-0c1d2e3f4a5b"` |
| `USER_ID` | UUID | User who initiated the scan | `"de787f14-f5c3-41cf-967d-9ce528b9bd75"` |
| `SUPABASE_URL` | URL | Supabase project URL | `"https://proj.supabase.co"` |
| `SUPABASE_SERVICE_ROLE_KEY` | String | Service role key (has elevated permissions) | `"eyJ..."` |

### Simple Mode Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `DOMAINS` | JSON Array | Domains to scan | `'["example.com", "test.com"]'` |
| `REDIS_HOST` | String | Redis server hostname | `"cache.amazonaws.com"` |
| `REDIS_PORT` | Integer | Redis server port | `"6379"` |
| `SCAN_TIMEOUT` | Integer | Timeout in minutes | `"10"` |

**Example**:
```bash
SCAN_JOB_ID="3f8e1a2b-4c5d-6e7f-8a9b-0c1d2e3f4a5b"
USER_ID="de787f14-f5c3-41cf-967d-9ce528b9bd75"
DOMAINS='["example.com", "test.com"]'
SUPABASE_URL="https://yourproject.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="eyJhbGc..."
REDIS_HOST="cache.amazonaws.com"
REDIS_PORT="6379"
SCAN_TIMEOUT="10"
```

### Batch Mode Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `BATCH_MODE` | Boolean | Enable batch mode | `"true"` |
| `BATCH_ID` | UUID | Batch job identifier | `"uuid"` |
| `ASSET_ID` | UUID | Asset being scanned | `"uuid"` |
| `BATCH_OFFSET` | Integer | Pagination offset for database fetch | `"0"`, `"200"` |
| `BATCH_LIMIT` | Integer | Number of records to fetch | `"200"` |
| `BATCH_DOMAINS` | JSON Array | Domains in this batch (alternative to DB fetch) | `'["example.com"]'` |

**Example**:
```bash
BATCH_MODE="true"
BATCH_ID="batch-uuid"
ASSET_ID="asset-uuid"
BATCH_OFFSET="0"
BATCH_LIMIT="200"
SCAN_JOB_ID="job-uuid"
USER_ID="user-uuid"
SUPABASE_URL="https://yourproject.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="eyJhbGc..."
```

### Streaming Mode Variables (Producer)

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `STREAMING_MODE` | Boolean | Enable streaming output | `"true"` |
| `STREAM_OUTPUT_KEY` | String | Redis Stream key for output | `"scan:{job_id}:subfinder:output"` |
| `REDIS_HOST` | String | Redis server hostname | `"cache.amazonaws.com"` |
| `REDIS_PORT` | Integer | Redis server port | `"6379"` |

**Example**:
```bash
STREAMING_MODE="true"
STREAM_OUTPUT_KEY="scan:3f8e1a2b:subfinder:output"
REDIS_HOST="cache.amazonaws.com"
REDIS_PORT="6379"
SCAN_JOB_ID="3f8e1a2b-4c5d-6e7f-8a9b-0c1d2e3f4a5b"
USER_ID="user-uuid"
DOMAINS='["example.com"]'
SUPABASE_URL="https://yourproject.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="eyJhbGc..."
```

### Streaming Mode Variables (Consumer)

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `STREAMING_MODE` | Boolean | Enable streaming input | `"true"` |
| `STREAM_INPUT_KEY` | String | Redis Stream key to read from | `"scan:{job_id}:subfinder:output"` |
| `CONSUMER_GROUP_NAME` | String | Redis consumer group | `"dnsx-consumers"` |
| `CONSUMER_NAME` | String | Unique consumer identifier | `"dnsx-task-abc123"` |
| `BATCH_SIZE` | Integer | Messages per XREADGROUP call | `"50"` |
| `BLOCK_MILLISECONDS` | Integer | XREADGROUP blocking time | `"5000"` |
| `MAX_PROCESSING_TIME` | Integer | Max consumption time (seconds) | `"3600"` |

**Example**:
```bash
STREAMING_MODE="true"
STREAM_INPUT_KEY="scan:3f8e1a2b:subfinder:output"
CONSUMER_GROUP_NAME="dnsx-consumers"
CONSUMER_NAME="dnsx-task-abc123"
BATCH_SIZE="50"
BLOCK_MILLISECONDS="5000"
MAX_PROCESSING_TIME="3600"
REDIS_HOST="cache.amazonaws.com"
REDIS_PORT="6379"
```

### Optional Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WORKERS` | Integer | `10` | Concurrent workers for parallel processing |
| `LOG_LEVEL` | String | `"info"` | Logging level: `debug`, `info`, `warn`, `error` |
| `HEALTH_CHECK_ENABLED` | Boolean | `"false"` | Enable HTTP health endpoint |
| `HEALTH_PORT` | Integer | `"8080"` | Health check endpoint port |
| `METRICS_COLLECTION_ENABLED` | Boolean | `"false"` | Enable performance metrics |

---

## Resource Scaling DSL

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["domain_count_ranges"],
  "properties": {
    "domain_count_ranges": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["min_domains", "max_domains", "cpu", "memory", "description"],
        "properties": {
          "min_domains": {
            "type": "integer",
            "minimum": 1,
            "description": "Minimum domains in this range (inclusive)"
          },
          "max_domains": {
            "type": "integer",
            "minimum": 1,
            "description": "Maximum domains in this range (inclusive)"
          },
          "cpu": {
            "type": "integer",
            "enum": [256, 512, 1024, 2048, 4096],
            "description": "ECS CPU units (256 = 0.25 vCPU)"
          },
          "memory": {
            "type": "integer",
            "minimum": 512,
            "maximum": 8192,
            "description": "ECS memory in MB"
          },
          "description": {
            "type": "string",
            "description": "Human-readable description of this range"
          }
        }
      }
    },
    "scaling_notes": {
      "type": "string",
      "description": "Additional notes about scaling behavior"
    }
  }
}
```

### Valid CPU/Memory Combinations (AWS Fargate)

| CPU (units) | vCPU | Valid Memory (MB) |
|-------------|------|-------------------|
| 256 | 0.25 | 512, 1024, 2048 |
| 512 | 0.5 | 1024, 2048, 3072, 4096 |
| 1024 | 1.0 | 2048, 3072, 4096, 5120, 6144, 7168, 8192 |
| 2048 | 2.0 | 4096, 5120, 6144, 7168, 8192, 9216, ..., 16384 |
| 4096 | 4.0 | 8192, 9216, ..., 30720 |

**Common Patterns**:

#### Light I/O Module (API calls, minimal processing)
```json
{
  "domain_count_ranges": [
    {"min_domains": 1, "max_domains": 10, "cpu": 256, "memory": 512, "description": "Light"},
    {"min_domains": 11, "max_domains": 50, "cpu": 512, "memory": 1024, "description": "Medium"},
    {"min_domains": 51, "max_domains": 200, "cpu": 1024, "memory": 2048, "description": "Heavy"}
  ],
  "scaling_notes": "API rate limits are primary bottleneck"
}
```

#### Medium Processing (DNS resolution, HTTP probing)
```json
{
  "domain_count_ranges": [
    {"min_domains": 1, "max_domains": 50, "cpu": 512, "memory": 1024, "description": "Small batch"},
    {"min_domains": 51, "max_domains": 200, "cpu": 1024, "memory": 2048, "description": "Medium batch"},
    {"min_domains": 201, "max_domains": 500, "cpu": 2048, "memory": 4096, "description": "Large batch"}
  ],
  "scaling_notes": "Scales linearly with domain count"
}
```

#### Heavy Computation (Vulnerability scanning, fuzzing)
```json
{
  "domain_count_ranges": [
    {"min_domains": 1, "max_domains": 10, "cpu": 1024, "memory": 2048, "description": "Light scan"},
    {"min_domains": 11, "max_domains": 50, "cpu": 2048, "memory": 4096, "description": "Heavy scan"},
    {"min_domains": 51, "max_domains": 100, "cpu": 4096, "memory": 8192, "description": "Very heavy"}
  ],
  "scaling_notes": "CPU-intensive template matching"
}
```

### Range Design Guidelines

1. **Non-Overlapping**: Ranges must not overlap
   - ✅ Good: `[1-10], [11-50], [51-200]`
   - ❌ Bad: `[1-10], [10-50]` (10 appears twice)

2. **Contiguous**: Ranges should cover expected workloads
   - ✅ Good: `[1-10], [11-50], [51-200]` (no gaps)
   - ⚠️ Warning: `[1-10], [20-50]` (gap: 11-19)

3. **Cost-Aware**: Higher resources = higher cost
   - 256 CPU, 512 MB: ~$0.003/hour
   - 4096 CPU, 8192 MB: ~$0.20/hour (67x more expensive)

4. **Realistic Maximums**: Set `max_domains` based on actual capacity
   - Don't claim 1000 domains/batch if module times out at 200

---

## Optimization Hints

### Standard Hints

**Purpose**: Module-specific configuration flags that control behavior

**Type**: `JSONB` (arbitrary key-value pairs)

### Common Hints Dictionary

| Hint Key | Type | Default | Description | Used By |
|----------|------|---------|-------------|---------|
| `requires_database_fetch` | Boolean | `false` | Module fetches input data from database | DNSx, HTTPx, Nuclei |
| `requires_asset_id` | Boolean | `false` | Module needs asset_id for data linkage | All modules |
| `streams_output` | Boolean | `false` | Module produces Redis Stream output | Subfinder, CT-Scanner |
| `consumes_stream` | Boolean | `false` | Module reads from Redis Stream input | DNSx, HTTPx |
| `high_cpu_usage` | Boolean | `false` | Module is CPU-intensive | Nuclei, WPScan |
| `high_memory_usage` | Boolean | `false` | Module needs extra memory | Nuclei (large template sets) |
| `api_rate_limited` | Boolean | `false` | Module limited by external API rates | Subfinder, CT-Scanner |
| `supports_resume` | Boolean | `false` | Module can resume from checkpoint | Future feature |

### Module-Specific Hints

**Subfinder Example**:
```json
{
  "requires_database_fetch": false,
  "requires_asset_id": true,
  "streams_output": true,
  "api_rate_limited": true,
  "sources": ["crt.sh", "virustotal", "censys"],
  "max_sources_per_domain": 15
}
```

**DNSx Example**:
```json
{
  "requires_database_fetch": true,
  "requires_asset_id": true,
  "consumes_stream": true,
  "streams_output": false,
  "dns_resolvers": ["8.8.8.8", "1.1.1.1"],
  "max_retries": 3,
  "timeout_seconds": 5
}
```

**Nuclei Example**:
```json
{
  "requires_database_fetch": true,
  "requires_asset_id": true,
  "high_cpu_usage": true,
  "high_memory_usage": true,
  "template_count": 3000,
  "severity_filters": ["critical", "high"],
  "max_requests_per_template": 100
}
```

### Auto-Configuration (Convention Over Configuration)

**Rule**: Modules with dependencies automatically get `requires_database_fetch=true`

**Implementation** (`backend/app/services/module_registry.py:180-210`):
```python
if module.dependencies and not module.optimization_hints.get('requires_database_fetch'):
    module.optimization_hints['requires_database_fetch'] = True
    module.optimization_hints['requires_asset_id'] = True
    logger.info(f"Auto-enabled database fetch for '{module_name}' (has dependencies)")
```

**Example**:
```sql
-- Manual configuration (explicit)
INSERT INTO scan_module_profiles (
    module_name, dependencies, optimization_hints
) VALUES (
    'dnsx', 
    ARRAY['subfinder'],
    '{"requires_database_fetch": true, "requires_asset_id": true}'::jsonb
);

-- Auto-configuration (implicit - backend adds flags automatically)
INSERT INTO scan_module_profiles (
    module_name, dependencies, optimization_hints
) VALUES (
    'dnsx',
    ARRAY['subfinder'],
    '{}'::jsonb  -- Empty, backend auto-adds required flags
);
```

---

## ECS Task Configuration

### Task Definition Structure

```json
{
  "family": "neobotnet-v2-dev-{module-name}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::{account}:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::{account}:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "{module-name}-scanner",
      "image": "{account}.dkr.ecr.{region}.amazonaws.com/neobotnet-v2-dev/{module-name}:latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/aws/ecs/neobotnet-v2-dev",
          "awslogs-region": "{region}",
          "awslogs-stream-prefix": "{module-name}"
        }
      },
      "environment": []
    }
  ]
}
```

### Runtime Overrides

**CPU and Memory** are overridden at runtime based on `resource_scaling`:

```python
response = ecs_client.run_task(
    cluster='neobotnet-v2-dev-cluster',
    taskDefinition=module_profile.task_definition_template,
    launchType='FARGATE',
    overrides={
        'cpu': str(allocated_cpu),      # e.g., "512"
        'memory': str(allocated_memory), # e.g., "1024"
        'containerOverrides': [{
            'name': container_name,
            'environment': [...]  # Injected at runtime
        }]
    }
)
```

### Network Configuration

**VPC**: Private subnets with NAT Gateway for outbound access

```python
networkConfiguration={
    'awsvpcConfiguration': {
        'subnets': [
            'subnet-abc123',  # Private subnet 1
            'subnet-def456'   # Private subnet 2
        ],
        'securityGroups': [
            'sg-xyz789'  # Egress-only security group
        ],
        'assignPublicIp': 'DISABLED'
    }
}
```

### IAM Roles

**Execution Role** (pulls image, writes logs):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

**Task Role** (module permissions - minimal by default):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/ecs/neobotnet-v2-dev:*"
    }
  ]
}
```

---

## Redis Conventions

### Stream Naming Pattern

**Format**: `scan:{scan_job_id}:{module_name}:{direction}`

**Examples**:
- `scan:3f8e1a2b:subfinder:output` - Subfinder produces subdomains
- `scan:3f8e1a2b:dnsx:output` - DNSx produces DNS records
- `scan:3f8e1a2b:httpx:output` - HTTPx produces HTTP probes

**Components**:
- `scan`: Constant prefix
- `{scan_job_id}`: First 8 chars or full UUID
- `{module_name}`: Module identifier (`subfinder`, `dnsx`, etc.)
- `{direction}`: `output` (producer) or `input` (consumer uses upstream's output)

### Consumer Group Naming

**Format**: `{module_name}-consumers`

**Examples**:
- `dnsx-consumers` - All DNSx consumers
- `httpx-consumers` - All HTTPx consumers

**Consumer Name** (unique per task):
**Format**: `{module_name}-task-{task_id}`

**Example**: `dnsx-task-abc123def456`

### Message Format (Producer)

**Subdomain Discovery**:
```json
{
  "subdomain": "api.example.com",
  "parent_domain": "example.com",
  "source": "subfinder",
  "discovered_at": "2025-11-19T12:34:56Z",
  "scan_job_id": "3f8e1a2b-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
  "asset_id": "asset-uuid"
}
```

**Completion Marker**:
```json
{
  "type": "completion",
  "module": "subfinder",
  "scan_job_id": "3f8e1a2b-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
  "timestamp": "2025-11-19T12:35:00Z",
  "total_results": 247
}
```

### TTL and Cleanup

**Stream Expiration**: 24 hours

```bash
# Automatic cleanup via Redis TTL
EXPIRE scan:3f8e1a2b:subfinder:output 86400
```

**Manual Cleanup**:
```bash
# Delete stream after consumption
DEL scan:3f8e1a2b:subfinder:output

# Trim stream to last 1000 messages
XTRIM scan:3f8e1a2b:subfinder:output MAXLEN ~ 1000
```

---

## Error Codes & Status Values

### Scan Status Values

| Status | Description | Terminal State | Can Retry |
|--------|-------------|----------------|-----------|
| `pending` | Scan queued, not started | ❌ | N/A |
| `running` | Scan in progress | ❌ | N/A |
| `completed` | Successfully finished | ✅ | No |
| `partial_failure` | Some assets failed | ✅ | Yes (failed assets) |
| `failed` | Complete failure | ✅ | Yes |
| `cancelled` | User-cancelled | ✅ | No |

### Batch Status Values

| Status | Description | Terminal State |
|--------|-------------|----------------|
| `pending` | Batch created, awaiting execution | ❌ |
| `running` | ECS task running | ❌ |
| `completed` | All domains processed | ✅ |
| `failed` | Task failed or error | ✅ |
| `cancelled` | Explicitly cancelled | ✅ |

### Module Discovery Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFound` | `module_name` not in `scan_module_profiles` | Check spelling, verify DB insertion |
| `ModuleInactive` | `is_active = false` | Set `is_active = true` in database |
| `DependencyMissing` | Required dependency not found | Install dependency module first |
| `CircularDependency` | Module A depends on B, B depends on A | Fix `dependencies` array |

### Resource Allocation Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `InvalidResourceScaling` | Malformed `resource_scaling` JSON | Validate against JSON schema |
| `DomainCountExceedsRange` | Domain count > highest range | Add higher range or enable batching |
| `InvalidCPUMemoryCombination` | CPU/memory not compatible (Fargate) | Use valid combinations table |

### ECS Execution Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `TaskFailedToStart` | Image pull error, resource unavailable | Check ECR permissions, task definition |
| `ContainerExitedNonZero` | Module crashed | Check CloudWatch logs for stack trace |
| `TaskTimeout` | Exceeded `estimated_duration` * 2 | Increase timeout or optimize module |

---

## Configuration Examples

### Complete Module Profile (Producer)

**Subfinder** - Subdomain enumeration:

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
    'subfinder',
    '1.0',
    true,
    200,
    '{
        "domain_count_ranges": [
            {"min_domains": 1, "max_domains": 10, "cpu": 256, "memory": 512, "description": "Light workload"},
            {"min_domains": 11, "max_domains": 50, "cpu": 512, "memory": 1024, "description": "Medium workload"},
            {"min_domains": 51, "max_domains": 200, "cpu": 1024, "memory": 2048, "description": "Heavy workload"}
        ],
        "scaling_notes": "Subfinder is I/O bound. API rate limits are primary constraint."
    }'::jsonb,
    120,
    'neobotnet-v2-dev-subfinder',
    'subfinder-scanner',
    ARRAY[]::text[],
    '{
        "requires_database_fetch": false,
        "requires_asset_id": true,
        "streams_output": true,
        "api_rate_limited": true,
        "sources": ["crt.sh", "virustotal", "censys", "shodan"],
        "max_concurrent_domains": 10
    }'::jsonb,
    true
);
```

### Complete Module Profile (Consumer)

**DNSx** - DNS resolution:

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
    'dnsx',
    '1.0',
    true,
    500,
    '{
        "domain_count_ranges": [
            {"min_domains": 1, "max_domains": 100, "cpu": 512, "memory": 1024, "description": "Small batch"},
            {"min_domains": 101, "max_domains": 300, "cpu": 1024, "memory": 2048, "description": "Medium batch"},
            {"min_domains": 301, "max_domains": 500, "cpu": 2048, "memory": 4096, "description": "Large batch"}
        ],
        "scaling_notes": "DNS resolution scales well. Network bandwidth is main bottleneck."
    }'::jsonb,
    60,
    'neobotnet-v2-dev-dnsx',
    'dnsx-scanner',
    ARRAY['subfinder'],
    '{
        "requires_database_fetch": true,
        "requires_asset_id": true,
        "consumes_stream": true,
        "streams_output": false,
        "dns_resolvers": ["8.8.8.8", "1.1.1.1", "208.67.222.222"],
        "max_retries": 3,
        "query_timeout_seconds": 5,
        "record_types": ["A", "AAAA", "CNAME", "MX", "TXT"]
    }'::jsonb,
    true
);
```

### Minimal Module Profile

**CT Scanner** - Certificate Transparency logs (minimal config):

```sql
INSERT INTO scan_module_profiles (
    module_name,
    version,
    resource_scaling,
    task_definition_template,
    container_name
) VALUES (
    'ct-scanner',
    '1.0',
    '{"domain_count_ranges": [{"min_domains": 1, "max_domains": 100, "cpu": 256, "memory": 512, "description": "Standard"}]}'::jsonb,
    'neobotnet-v2-dev-ct-scanner',
    'ct-scanner'
);
-- Defaults: supports_batching=false, max_batch_size=1, dependencies=[], optimization_hints={}, is_active=true
```

---

**Document Version**: 1.0  
**Last Updated**: November 19, 2025  
**Previous**: [← Module Implementation Guide](03-IMPLEMENTING-A-MODULE.md) | **Next**: [Data Flow & Streaming →](05-DATA-FLOW-AND-STREAMING.md)
