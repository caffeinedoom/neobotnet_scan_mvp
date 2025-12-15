# Module System Deep Dive

**Template-Based Architecture for Extensible Reconnaissance**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Module Lifecycle](#module-lifecycle)
3. [Template Components](#template-components)
4. [Module Discovery & Validation](#module-discovery--validation)
5. [Resource Scaling System](#resource-scaling-system)
6. [Producer vs Consumer Patterns](#producer-vs-consumer-patterns)
7. [Dependency Resolution](#dependency-resolution)
8. [Module Configuration Patterns](#module-configuration-patterns)
9. [Best Practices & Anti-Patterns](#best-practices--anti-patterns)

---

## Introduction

The NeoBot-Net v2 module system is a **database-driven template architecture** that enables engineers to add reconnaissance capabilities without modifying backend code. This document explains the internals of how modules are discovered, validated, executed, and monitored.

### Key Principles

1. **Database as Schema Registry**: `scan_module_profiles` table defines module capabilities
2. **Container Isolation**: Each module is a standalone binary with defined I/O contracts
3. **Convention Over Configuration**: Intelligent defaults minimize required configuration
4. **Type Safety**: Pydantic models validate module profiles at runtime

### What Constitutes a Module?

A module is a **collection of artifacts that conform to the template contract**:

```
Module Artifacts:
  ├─ Database Profile (scan_module_profiles row)
  ├─ Container Image (ECR repository)
  ├─ ECS Task Definition (Terraform-managed)
  ├─ Go Binary (scanner implementation)
  └─ Documentation (optional README)
```

**Example**: The Subfinder module consists of:
- Database row: `module_name='subfinder'`, `container_name='subfinder-scanner'`
- Container: `neobotnet-v2-dev-subfinder:latest` in ECR
- Task Definition: `arn:aws:ecs:us-east-1:account:task-definition/neobotnet-v2-dev-subfinder`
- Binary: `/backend/containers/subfinder-go/` (main.go, scanner.go, etc.)

---

## Module Lifecycle

### Lifecycle Phases

```
┌─────────────────────────────────────────────────────────────────┐
│                     MODULE LIFECYCLE                            │
└─────────────────────────────────────────────────────────────────┘

1. REGISTRATION
   └─ Database: INSERT INTO scan_module_profiles (...)
   
2. DISCOVERY (Startup)
   └─ Backend: ModuleConfigLoader.initialize()
      └─ Query scan_module_profiles WHERE is_active = true
      └─ Build in-memory cache (dependencies, resources)
   
3. VALIDATION (Request Time)
   └─ API Request: POST /api/v1/scans {"modules": ["subfinder"]}
   └─ ModuleRegistry.validate_modules()
      ├─ Check module exists and is_active
      ├─ Verify dependencies are satisfied
      └─ Validate resource scaling configuration
   
4. RESOURCE ALLOCATION
   └─ ResourceCalculator.calculate_resources(module, domain_count)
      └─ Query resource_scaling.domain_count_ranges
      └─ Select CPU/memory based on workload
   
5. EXECUTION
   └─ BatchWorkflowOrchestrator.launch_ecs_task()
      ├─ Build container overrides (env vars, resources)
      ├─ Call ECS RunTask API
      └─ Monitor task via ECS DescribeTasks
   
6. MONITORING (Real-Time)
   └─ Module streams results to Redis
   └─ WebSocketManager pushes to frontend
   └─ Database records scan progress
   
7. COMPLETION
   └─ Module sends completion marker to Redis
   └─ Update scan_jobs.status = 'completed'
   └─ Cleanup Redis streams (24h TTL)
```

### State Transitions

**Module Profile States**:
- `is_active=true`: Module available for use
- `is_active=false`: Module hidden from discovery (soft delete)

**Scan Job States** (`scan_jobs.status`):
- `pending` → `running` → `completed`
- `pending` → `running` → `failed`
- `pending` → `cancelled` (user-triggered)

### Registration Process

**Step 1**: Insert module profile into database

```sql
-- TEMPLATE PATTERN: Module Registration
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
    'nuclei',                          -- Unique module identifier
    '1.0',                             -- Semantic version
    true,                              -- Supports batch processing
    100,                               -- Max domains per batch
    '{
        "domain_count_ranges": [
            {"min_domains": 1, "max_domains": 10, "cpu": 512, "memory": 1024, "description": "Light scan"},
            {"min_domains": 11, "max_domains": 50, "cpu": 1024, "memory": 2048, "description": "Medium scan"},
            {"min_domains": 51, "max_domains": 100, "cpu": 2048, "memory": 4096, "description": "Heavy scan"}
        ],
        "scaling_notes": "Nuclei is CPU-intensive for template matching"
    }'::jsonb,
    300,                               -- 5 minutes per domain estimate
    'neobotnet-v2-dev-nuclei',        -- ECS task definition family
    'nuclei-scanner',                  -- Container name in task def
    ARRAY['httpx'],                    -- Depends on HTTPx (needs HTTP probes)
    '{
        "requires_database_fetch": true,
        "requires_asset_id": true,
        "vulnerability_scanning": true
    }'::jsonb,
    true                               -- Active
);
```

**Step 2**: Backend auto-discovers on next startup or cache refresh

```python
# backend/app/main.py (startup event)
from app.services.module_config_loader import initialize_module_config

@app.on_event("startup")
async def startup_event():
    supabase = get_supabase_client()
    await initialize_module_config(supabase)
    # Nuclei module now available for use
```

**No backend deployment required** - module is immediately available after database insert and service restart (or cache expiry).

---

## Template Components

### 1. Database Profile (`scan_module_profiles`)

**Schema** (PostgreSQL):

```sql
CREATE TABLE scan_module_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identity
    module_name TEXT NOT NULL UNIQUE,
    version TEXT DEFAULT '1.0' NOT NULL,
    
    -- Batching Capabilities
    supports_batching BOOLEAN DEFAULT false NOT NULL,
    max_batch_size INTEGER DEFAULT 1 NOT NULL CHECK (max_batch_size >= 1),
    
    -- Resource Allocation
    resource_scaling JSONB NOT NULL,
    estimated_duration_per_domain INTEGER DEFAULT 120 NOT NULL CHECK (estimated_duration_per_domain > 0),
    
    -- ECS Integration
    task_definition_template TEXT NOT NULL,
    container_name TEXT NOT NULL,
    
    -- Dependency Graph
    dependencies TEXT[] DEFAULT '{}' NOT NULL,
    
    -- Module-Specific Flags
    optimization_hints JSONB DEFAULT '{}',
    
    -- Lifecycle
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
```

**Field Descriptions**:

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `module_name` | TEXT | Unique identifier | `"subfinder"`, `"dnsx"` |
| `version` | TEXT | Semantic version for compatibility | `"1.0"`, `"2.3.1"` |
| `supports_batching` | BOOLEAN | Can process multiple domains in one task | `true` (Subfinder), `false` (single-domain tools) |
| `max_batch_size` | INTEGER | Maximum domains per batch | `200` (Subfinder), `1` (no batching) |
| `resource_scaling` | JSONB | CPU/memory allocation rules | See [Resource Scaling](#resource-scaling-system) |
| `estimated_duration_per_domain` | INTEGER | Seconds per domain (for timeout calculation) | `120` (Subfinder), `60` (DNSx) |
| `task_definition_template` | TEXT | ECS task definition ARN or family name | `"neobotnet-v2-dev-subfinder"` |
| `container_name` | TEXT | Container name within task definition | `"subfinder-scanner"` |
| `dependencies` | TEXT[] | Modules that must execute first | `["subfinder"]` (for DNSx) |
| `optimization_hints` | JSONB | Module-specific configuration flags | `{"requires_database_fetch": true}` |

### 2. Container Implementation

**Directory Structure** (Template):

```
backend/containers/<module>-go/
├── main.go                    # Entry point, mode routing
├── scanner.go                 # Core scan logic
├── database.go                # Supabase client, persistence
├── batch_support.go           # Batch mode implementation
├── streaming.go               # Redis Streams producer/consumer (optional)
├── Dockerfile                 # Container build instructions
├── go.mod                     # Go dependencies
├── go.sum                     # Dependency lock file
└── README.md                  # Module documentation
```

**Required Files**:

#### `main.go` - Execution Mode Router

```go
// TEMPLATE PATTERN: Module Entry Point
package main

import (
    "log"
    "os"
)

func main() {
    // 1. Determine execution mode from environment
    batchMode := os.Getenv("BATCH_MODE") == "true"
    streamingMode := os.Getenv("STREAMING_MODE") == "true"
    
    log.Printf("🚀 Module starting: %s mode", getModeName(batchMode, streamingMode))
    
    // 2. Validate required environment variables
    if err := validateRequiredEnvVars(batchMode, streamingMode); err != nil {
        log.Fatalf("❌ Environment validation failed: %v", err)
    }
    
    // 3. Route to appropriate handler
    if streamingMode {
        if err := runStreamingMode(); err != nil {
            log.Fatalf("❌ Streaming mode failed: %v", err)
        }
        return
    }
    
    if batchMode {
        if err := runBatchMode(); err != nil {
            log.Fatalf("❌ Batch mode failed: %v", err)
        }
        return
    }
    
    // Default: Simple mode (for testing)
    if err := runSimpleMode(); err != nil {
        log.Fatalf("❌ Simple mode failed: %v", err)
    }
}

// TEMPLATE PATTERN: Environment Validation
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
```

#### `scanner.go` - Core Scan Logic

```go
// TEMPLATE PATTERN: Scanner Implementation
package main

import (
    "context"
    "log"
    "time"
    // Module-specific imports
)

type Scanner struct {
    config         *Config
    redisClient    *redis.Client
    supabaseClient *SupabaseClient
    logger         *log.Logger
    ctx            context.Context
    cancel         context.CancelFunc
}

// TEMPLATE PATTERN: Scanner Initialization
func NewScanner(config *Config) (*Scanner, error) {
    ctx, cancel := context.WithTimeout(
        context.Background(), 
        time.Duration(config.Timeout)*time.Minute,
    )
    
    redisClient := redis.NewClient(&redis.Options{
        Addr: fmt.Sprintf("%s:%s", config.RedisHost, config.RedisPort),
    })
    
    if err := redisClient.Ping(ctx).Err(); err != nil {
        cancel()
        return nil, fmt.Errorf("redis connection failed: %w", err)
    }
    
    supabaseClient, err := NewSupabaseClient()
    if err != nil {
        cancel()
        return nil, fmt.Errorf("supabase initialization failed: %w", err)
    }
    
    return &Scanner{
        config:         config,
        redisClient:    redisClient,
        supabaseClient: supabaseClient,
        logger:         log.New(os.Stdout, "[Scanner] ", log.LstdFlags),
        ctx:            ctx,
        cancel:         cancel,
    }, nil
}

// TEMPLATE PATTERN: Main Scan Logic
func (s *Scanner) Run() error {
    s.logger.Printf("🎯 Starting scan for %d domains", len(s.config.Domains))
    
    results := []ScanResult{}
    
    for _, domain := range s.config.Domains {
        // Check context for cancellation
        select {
        case <-s.ctx.Done():
            return fmt.Errorf("scan cancelled or timed out")
        default:
        }
        
        // Execute module-specific scan logic
        result, err := s.scanDomain(domain)
        if err != nil {
            s.logger.Printf("⚠️  Failed to scan %s: %v", domain, err)
            continue
        }
        
        results = append(results, result...)
    }
    
    // Persist results or stream to Redis
    if s.config.StreamingMode {
        return s.streamResults(results)
    }
    
    return s.persistResults(results)
}

// Module-specific implementation
func (s *Scanner) scanDomain(domain string) ([]ScanResult, error) {
    // TODO: Implement your scan logic here
    // Examples:
    //   - Subfinder: passive subdomain enumeration
    //   - DNSx: DNS resolution and record extraction
    //   - HTTPx: HTTP probing and fingerprinting
    return nil, nil
}
```

#### `database.go` - Persistence Layer

```go
// TEMPLATE PATTERN: Database Client
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "os"
)

type SupabaseClient struct {
    URL        string
    ServiceKey string
    HTTPClient *http.Client
}

func NewSupabaseClient() (*SupabaseClient, error) {
    url := os.Getenv("SUPABASE_URL")
    key := os.Getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if url == "" || key == "" {
        return nil, fmt.Errorf("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    }
    
    return &SupabaseClient{
        URL:        url,
        ServiceKey: key,
        HTTPClient: &http.Client{Timeout: 30 * time.Second},
    }, nil
}

// TEMPLATE PATTERN: Bulk Insert with Conflict Resolution
func (c *SupabaseClient) BulkInsert(table string, records []interface{}) error {
    data, _ := json.Marshal(records)
    
    req, _ := http.NewRequest("POST", 
        fmt.Sprintf("%s/rest/v1/%s", c.URL, table), 
        bytes.NewBuffer(data))
    
    req.Header.Set("apikey", c.ServiceKey)
    req.Header.Set("Authorization", "Bearer "+c.ServiceKey)
    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("Prefer", "resolution=merge-duplicates")
    
    resp, err := c.HTTPClient.Do(req)
    if err != nil {
        return fmt.Errorf("request failed: %w", err)
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != 201 {
        return fmt.Errorf("unexpected status: %d", resp.StatusCode)
    }
    
    return nil
}
```

### 3. ECS Task Definition

**Managed via Terraform** (`infrastructure/terraform/ecs.tf`):

```hcl
# TEMPLATE PATTERN: ECS Task Definition for Module
resource "aws_ecs_task_definition" "module" {
  family                   = "neobotnet-v2-dev-${var.module_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"  # Default, overridden at runtime
  memory                   = "512"  # Default, overridden at runtime
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${var.module_name}-scanner"
      image     = "${aws_ecr_repository.module.repository_url}:latest"
      essential = true
      
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/aws/ecs/neobotnet-v2-dev"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = var.module_name
        }
      }
      
      environment = []  # Populated at runtime via containerOverrides
    }
  ])
}
```

**Runtime Override** (in `batch_workflow_orchestrator.py`):

```python
# TEMPLATE PATTERN: ECS Task Launch with Overrides
response = ecs_client.run_task(
    cluster='neobotnet-v2-dev-cluster',
    taskDefinition=module_profile.task_definition_template,
    launchType='FARGATE',
    overrides={
        'cpu': str(allocated_cpu),         # Override default CPU
        'memory': str(allocated_memory),   # Override default memory
        'containerOverrides': [{
            'name': module_profile.container_name,
            'environment': [
                {'name': 'SCAN_JOB_ID', 'value': scan_job_id},
                {'name': 'USER_ID', 'value': user_id},
                {'name': 'ASSET_ID', 'value': asset_id},
                {'name': 'DOMAINS', 'value': json.dumps(domains)},
                {'name': 'BATCH_MODE', 'value': 'true' if batch_mode else 'false'},
                {'name': 'STREAMING_MODE', 'value': 'true' if streaming else 'false'},
                {'name': 'STREAM_OUTPUT_KEY', 'value': f'scan:{scan_job_id}:{module_name}:output'},
                # Module-specific env vars can be added here
            ]
        }]
    },
    networkConfiguration={...}
)
```

---

## Module Discovery & Validation

### Discovery Mechanism

**At Application Startup**:

```python
# backend/app/main.py
from app.services.module_config_loader import initialize_module_config
from app.core.supabase_client import get_supabase_client

@app.on_event("startup")
async def startup_event():
    logger.info("🔄 Loading module configuration from database...")
    supabase = get_supabase_client()
    await initialize_module_config(supabase)
    logger.info("✅ Module configuration loaded")
```

**ModuleConfigLoader Implementation** (`backend/app/services/module_config_loader.py:53-104`):

```python
async def initialize(self, supabase_client) -> None:
    """
    Load module configuration from database on app startup.
    
    Queries the scan_module_profiles table for all active modules and
    builds internal caches for fast lookups.
    """
    logger.info("🔄 Loading module configuration from database...")
    
    try:
        # Query scan_module_profiles table for active modules
        response = supabase_client.table('scan_module_profiles').select(
            'module_name, container_name, dependencies, is_active'
        ).eq('is_active', True).order('module_name').execute()
        
        rows = response.data
        
        if not rows:
            logger.warning("⚠️  No active modules found in scan_module_profiles!")
            self._dependencies = {}
            self._container_names = {}
            self._modules_cache = []
            self._initialized = True
            return
        
        # Build configuration dictionaries
        self._dependencies = {}
        self._container_names = {}
        self._modules_cache = []
        
        for row in rows:
            module_name = row['module_name']
            self._dependencies[module_name] = row.get('dependencies') or []
            self._container_names[module_name] = row['container_name']
            self._modules_cache.append(module_name)
        
        self._initialized = True
        
        logger.info(f"✅ Loaded {len(rows)} active modules: {', '.join(sorted(self._modules_cache))}")
        logger.debug(f"   Dependencies: {self._dependencies}")
        logger.debug(f"   Container names: {self._container_names}")
        
    except Exception as e:
        logger.error(f"❌ Failed to load module configuration: {e}")
        raise
```

**Result**: All active modules are cached in memory for fast lookup during request handling.

### Validation Process

**Request-Time Validation** (`backend/app/services/module_registry.py:247-354`):

```python
async def validate_modules(self, module_names: List[str]) -> Dict[str, bool]:
    """
    Validate multiple modules exist and are active.
    
    Args:
        module_names: List of module names to validate
        
    Returns:
        Dict mapping module_name -> is_valid
        
    Example:
        >>> await registry.validate_modules(['subfinder', 'dnsx', 'invalid'])
        {'subfinder': True, 'dnsx': True, 'invalid': False}
    """
    results = {}
    
    for module_name in module_names:
        try:
            module = await self.get_module(module_name)
            results[module_name] = module is not None and module.is_active
        except Exception as e:
            logger.error(f"Validation failed for {module_name}: {e}")
            results[module_name] = False
    
    return results
```

**Validation Checks**:
1. **Existence**: Module row exists in `scan_module_profiles`
2. **Active Status**: `is_active = true`
3. **Dependencies**: All dependency modules are also active
4. **Resource Scaling**: `resource_scaling` JSON is valid
5. **ECS Task Definition**: Template references valid task definition

**Failure Handling**:
```python
# API endpoint validation (backend/app/api/v1/scans.py)
validation_results = await module_registry.validate_modules(request.modules)

invalid_modules = [m for m, valid in validation_results.items() if not valid]
if invalid_modules:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid or inactive modules: {', '.join(invalid_modules)}"
    )
```

---

## Resource Scaling System

### Scaling Configuration DSL

**JSON Schema** (`resource_scaling` JSONB column):

```json
{
  "domain_count_ranges": [
    {
      "min_domains": 1,
      "max_domains": 10,
      "cpu": 256,
      "memory": 512,
      "description": "Light workload - single domains or small batches"
    },
    {
      "min_domains": 11,
      "max_domains": 50,
      "cpu": 512,
      "memory": 1024,
      "description": "Medium workload - typical asset scans"
    },
    {
      "min_domains": 51,
      "max_domains": 200,
      "cpu": 1024,
      "memory": 2048,
      "description": "Heavy workload - large enterprise assets"
    },
    {
      "min_domains": 201,
      "max_domains": 1000,
      "cpu": 2048,
      "memory": 4096,
      "description": "Very heavy workload - batch optimization required"
    }
  ],
  "scaling_notes": "Subfinder scales linearly with domain count. API rate limits are the bottleneck, not CPU."
}
```

**Design Rationale**:
- **Ranges Not Fixed Points**: Domain counts vary, ranges provide flexibility
- **Non-Overlapping**: Ranges must be contiguous and cover expected workload spectrum
- **ECS Constraints**: CPU must be 256/512/1024/2048/4096, memory must be compatible
- **Cost Awareness**: Larger allocations = higher cost, optimize for typical workloads

### Resource Calculator

**Implementation** (`backend/app/services/resource_calculator.py`):

```python
# TEMPLATE PATTERN: Resource Allocation Algorithm
def calculate_resources(
    module_profile: ModuleProfile,
    domain_count: int
) -> ResourceAllocation:
    """
    Calculate optimal CPU and memory allocation based on domain count.
    
    Algorithm:
      1. Query module's resource_scaling.domain_count_ranges
      2. Find range where min_domains <= count <= max_domains
      3. Return corresponding CPU/memory
      4. Estimate duration: domain_count * estimated_duration_per_domain
    
    Args:
        module_profile: Module metadata from scan_module_profiles
        domain_count: Number of domains to process
        
    Returns:
        ResourceAllocation with cpu, memory, estimated_duration
        
    Raises:
        ValueError: If domain_count exceeds max supported range
    """
    scaling_config = module_profile.resource_scaling
    
    for range_config in scaling_config['domain_count_ranges']:
        if (range_config['min_domains'] <= domain_count <= range_config['max_domains']):
            return ResourceAllocation(
                cpu=range_config['cpu'],
                memory=range_config['memory'],
                estimated_duration_minutes=ceil(
                    (domain_count * module_profile.estimated_duration_per_domain) / 60.0
                ),
                description=range_config['description'],
                domain_count=domain_count,
                module_name=module_profile.module_name
            )
    
    # Fallback: Use highest range
    max_range = max(scaling_config['domain_count_ranges'], 
                    key=lambda r: r['max_domains'])
    
    logger.warning(
        f"Domain count {domain_count} exceeds max range for {module_profile.module_name}. "
        f"Using maximum allocation: {max_range['cpu']} CPU, {max_range['memory']} MB memory. "
        f"Consider batch optimization."
    )
    
    return ResourceAllocation(
        cpu=max_range['cpu'],
        memory=max_range['memory'],
        estimated_duration_minutes=ceil(
            (domain_count * module_profile.estimated_duration_per_domain) / 60.0
        ),
        description="Maximum allocation (exceeds typical range)",
        domain_count=domain_count,
        module_name=module_profile.module_name
    )
```

**Example Calculation**:

```python
# Subfinder with 25 domains
module = await module_registry.get_module('subfinder')
resources = resource_calculator.calculate_resources(module, domain_count=25)

# Result:
ResourceAllocation(
    cpu=512,                      # From "11-50 domains" range
    memory=1024,
    estimated_duration_minutes=5,  # 25 domains * 120 seconds / 60
    description="Medium workload - typical asset scans",
    domain_count=25,
    module_name="subfinder"
)
```

### Cost Optimization

**Batch Optimizer** (`backend/app/services/batch_optimizer.py`):

**Problem**: 500 domains in separate tasks = 500 * $0.003 = $1.50

**Solution**: Batch into groups of 200 = 3 tasks * $0.008 = $0.024 (96% savings)

```python
def optimize_batches(
    module_profile: ModuleProfile,
    domains: List[str]
) -> List[BatchConfig]:
    """
    Optimize domain distribution into cost-efficient batches.
    
    Algorithm:
      1. Get module's max_batch_size
      2. Calculate optimal batch sizes to minimize tasks
      3. Ensure last batch isn't tiny (merge if < 30% of max)
    
    Example:
        Input: 450 domains, max_batch_size=200
        Output: [200, 200, 50] → 3 tasks instead of 450
    """
    max_size = module_profile.max_batch_size
    batches = []
    remaining = len(domains)
    
    while remaining > 0:
        if remaining <= max_size:
            batches.append(remaining)
            break
        elif remaining <= max_size * 1.3:  # Within 30% of max
            # Split evenly to avoid tiny last batch
            batch_size = remaining // 2
            batches.extend([batch_size, remaining - batch_size])
            break
        else:
            batches.append(max_size)
            remaining -= max_size
    
    return batches
```

---

## Producer vs Consumer Patterns

### Producer Modules

**Characteristics**:
- Generate new data (e.g., subdomains, IPs, vulnerabilities)
- No dependencies (or depend only on static data like asset domains)
- Stream results to Redis for downstream consumption
- Example: Subfinder (discovers subdomains)

**Streaming Implementation** (`backend/containers/subfinder-go/scanner.go:450-540`):

```go
// TEMPLATE PATTERN: Producer Streaming
func (s *Scanner) streamSubdomainsToRedis(result *DomainScanResult) error {
    if s.config.StreamOutputKey == "" {
        return fmt.Errorf("stream output key not configured")
    }
    
    s.logger.Infof("📤 Streaming %d subdomains to Redis: %s", 
        len(result.Subdomains), s.config.StreamOutputKey)
    
    for _, subdomain := range result.Subdomains {
        // XADD to Redis Stream
        _, err := s.redisClient.XAdd(s.ctx, &redis.XAddArgs{
            Stream: s.config.StreamOutputKey,
            Values: map[string]interface{}{
                "subdomain":      subdomain.Subdomain,
                "source":         subdomain.Source,
                "discovered_at":  subdomain.DiscoveredAt,
                "parent_domain":  subdomain.ParentDomain,
                "scan_job_id":    s.config.JobID,
                "asset_id":       subdomain.AssetID,
            },
        }).Result()
        
        if err != nil {
            s.logger.Errorf("Failed to stream subdomain %s: %v", subdomain.Subdomain, err)
            continue
        }
    }
    
    // Send completion marker
    return s.sendCompletionMarker(len(result.Subdomains))
}

// TEMPLATE PATTERN: Completion Marker
func (s *Scanner) sendCompletionMarker(totalResults int) error {
    _, err := s.redisClient.XAdd(s.ctx, &redis.XAddArgs{
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
    
    s.logger.Infof("✅ Sent completion marker: %d total subdomains", totalResults)
    return nil
}
```

### Consumer Modules

**Characteristics**:
- Enrich existing data (e.g., resolve DNS for subdomains, probe HTTP)
- Depend on upstream modules (declared in `dependencies` array)
- Consume from Redis Streams or database
- Example: DNSx (consumes subdomains from Subfinder, adds DNS records)

**Streaming Consumer Implementation** (`backend/containers/dnsx-go/streaming.go:120-250`):

```go
// TEMPLATE PATTERN: Consumer Streaming
func consumeStream(
    redisClient *redis.Client,
    ctx context.Context,
    config *StreamingConfig,
    dnsxClient *dnsx.DNSX,
    supabaseClient *SupabaseClient,
) error {
    processedCount := 0
    completionReceived := false
    
    log.Printf("🔄 Starting stream consumption loop...")
    log.Printf("  • Reading from: %s", config.StreamInputKey)
    log.Printf("  • Consumer: %s in group %s", config.ConsumerName, config.ConsumerGroupName)
    
    for {
        // Check if completed
        if completionReceived {
            log.Println("✅ Completion marker received, exiting")
            break
        }
        
        // Check timeout
        if time.Since(startTime) > config.MaxProcessingTime {
            log.Printf("⚠️  Max processing time exceeded, stopping")
            break
        }
        
        // Read messages from stream using XREADGROUP
        streams, err := redisClient.XReadGroup(ctx, &redis.XReadGroupArgs{
            Group:    config.ConsumerGroupName,
            Consumer: config.ConsumerName,
            Streams:  []string{config.StreamInputKey, ">"},  // ">" = only new messages
            Count:    config.BatchSize,                       // Read 50 at a time
            Block:    time.Duration(config.BlockMilliseconds) * time.Millisecond,
        }).Result()
        
        if err != nil {
            if err == redis.Nil {
                continue  // No new messages, keep waiting
            }
            return fmt.Errorf("XREADGROUP failed: %w", err)
        }
        
        if len(streams) == 0 {
            continue
        }
        
        // Process each message
        for _, message := range streams[0].Messages {
            // Parse message
            msgType := message.Values["type"]
            
            if msgType == "completion" {
                log.Println("📋 Received completion marker")
                completionReceived = true
                
                // Acknowledge and stop consuming
                redisClient.XAck(ctx, config.StreamInputKey, 
                    config.ConsumerGroupName, message.ID)
                break
            }
            
            // Parse subdomain message
            subdomain := SubdomainMessage{
                Subdomain:    message.Values["subdomain"].(string),
                Source:       message.Values["source"].(string),
                ParentDomain: message.Values["parent_domain"].(string),
                AssetID:      message.Values["asset_id"].(string),
            }
            
            // Process: Resolve DNS
            dnsRecords, err := resolveDNS(subdomain.Subdomain, dnsxClient)
            if err != nil {
                log.Printf("⚠️  DNS resolution failed for %s: %v", subdomain.Subdomain, err)
            } else {
                // Write to database
                supabaseClient.InsertDNSRecords(dnsRecords)
                processedCount++
            }
            
            // Acknowledge message
            redisClient.XAck(ctx, config.StreamInputKey, 
                config.ConsumerGroupName, message.ID)
        }
    }
    
    log.Printf("✅ Processed %d subdomains", processedCount)
    return nil
}
```

**Key Differences**:

| Aspect | Producer | Consumer |
|--------|----------|----------|
| **Dependencies** | `[]` (empty) | `["upstream_module"]` |
| **Redis Operation** | `XADD` (write) | `XREADGROUP` (read) |
| **Data Source** | Environment vars or database | Redis Stream |
| **Completion** | Sends marker | Waits for marker |
| **Execution** | Can run solo | Requires upstream completion |

---

## Dependency Resolution

### Dependency Graph

**Example Dependency Chain**:

```
Subfinder (no deps)
    ↓ produces subdomains
DNSx (depends on Subfinder)
    ↓ produces DNS records
HTTPx (depends on DNSx)
    ↓ produces HTTP probes
Nuclei (depends on HTTPx)
    ↓ produces vulnerabilities
```

**Database Representation**:

```sql
SELECT module_name, dependencies FROM scan_module_profiles;

module_name | dependencies
------------|-------------
subfinder   | {}
dnsx        | {subfinder}
httpx       | {dnsx}
nuclei      | {httpx}
```

### Resolution Algorithm

**Topological Sort** (`backend/app/services/scan_pipeline.py:96-168`):

```python
def _resolve_execution_order(self, modules: List[str]) -> List[str]:
    """
    Topological sort of modules based on dependencies using DFS.
    
    Auto-includes required persistence modules (e.g., DNSx with Subfinder).
    
    Args:
        modules: List of module names (unordered)
        
    Returns:
        Ordered list (dependencies first)
        
    Raises:
        DependencyError: If circular dependency detected
        
    Example:
        Input: ["httpx", "subfinder", "nuclei"]
        Output: ["subfinder", "dnsx", "httpx", "nuclei"]
        (dnsx auto-included for persistence)
    """
    # Phase 1: Auto-include DNSx when Subfinder present
    modules_set = set(modules)
    if "subfinder" in modules_set and "dnsx" not in modules_set:
        self.logger.info(
            "🔧 Auto-including 'dnsx' module: "
            "Subfinder requires DNSx for data persistence"
        )
        modules_set.add("dnsx")
    
    modules = list(modules_set)
    
    # Phase 2: Topological sort with cycle detection
    ordered = []
    visited = set()
    visiting = set()  # Track recursion stack for cycle detection
    
    def visit(module: str):
        if module in visited:
            return
        if module in visiting:
            raise DependencyError(
                f"Circular dependency detected involving module: {module}"
            )
        
        visiting.add(module)
        
        # Visit dependencies first (recursion)
        try:
            deps = get_module_config().get_dependencies(module)
        except ValueError:
            deps = []
        
        for dep in deps:
            if dep in modules:
                visit(dep)  # Recurse into dependency
            else:
                self.logger.warning(
                    f"⚠️  Module {module} requires {dep}, but {dep} not in scan request. "
                    f"This may cause {module} to fail."
                )
        
        visiting.remove(module)
        visited.add(module)
        ordered.append(module)
    
    # Visit each module in request
    for module in modules:
        visit(module)
    
    return ordered
```

**Execution Example**:

```python
# User requests: ["httpx", "subfinder"]
requested_modules = ["httpx", "subfinder"]

# Step 1: Auto-include DNSx (persistence requirement)
# modules_set = {"subfinder", "httpx", "dnsx"}

# Step 2: Topological sort
# visit("httpx"):
#   deps = ["dnsx"] → visit("dnsx"):
#     deps = ["subfinder"] → visit("subfinder"):
#       deps = [] → ordered = ["subfinder"]
#     ordered = ["subfinder", "dnsx"]
#   ordered = ["subfinder", "dnsx", "httpx"]

execution_order = ["subfinder", "dnsx", "httpx"]
```

---

## Module Configuration Patterns

### Pattern 1: Standalone Producer

**Use Case**: Module generates data with no dependencies

**Example**: Subfinder, SSL Certificate Transparency Log Scanner

**Configuration**:

```json
{
  "module_name": "subfinder",
  "dependencies": [],
  "supports_batching": true,
  "max_batch_size": 200,
  "optimization_hints": {
    "requires_database_fetch": false,  // Gets domains from env vars
    "requires_asset_id": true,         // Needs asset_id for data linkage
    "streams_output": true             // Produces Redis Stream
  }
}
```

### Pattern 2: Dependent Consumer

**Use Case**: Module enriches data from upstream module

**Example**: DNSx, HTTPx, Nuclei

**Configuration**:

```json
{
  "module_name": "dnsx",
  "dependencies": ["subfinder"],
  "supports_batching": true,
  "max_batch_size": 500,
  "optimization_hints": {
    "requires_database_fetch": true,   // Fetches subdomains from DB
    "requires_asset_id": true,
    "consumes_stream": true,           // Can consume Redis Stream
    "streams_output": false            // Writes directly to DB
  }
}
```

**Auto-Configuration** (Convention over Configuration):

```python
# backend/app/services/module_registry.py:180-210
if module.dependencies and not module.optimization_hints.get('requires_database_fetch'):
    # CONVENTION: Modules with dependencies auto-enable database fetch
    module.optimization_hints['requires_database_fetch'] = True
    module.optimization_hints['requires_asset_id'] = True
    logger.info(f"📋 Auto-enabled database fetch for '{module_name}' (has dependencies)")
```

### Pattern 3: Heavy Computation Module

**Use Case**: CPU/memory-intensive processing (vulnerability scanning, fuzzing)

**Example**: Nuclei, WPScan, Nmap

**Configuration**:

```json
{
  "module_name": "nuclei",
  "dependencies": ["httpx"],
  "supports_batching": true,
  "max_batch_size": 50,  // Lower batch size due to intensity
  "resource_scaling": {
    "domain_count_ranges": [
      {"min_domains": 1, "max_domains": 10, "cpu": 1024, "memory": 2048},
      {"min_domains": 11, "max_domains": 50, "cpu": 2048, "memory": 4096}
    ]
  },
  "estimated_duration_per_domain": 600,  // 10 minutes per domain
  "optimization_hints": {
    "requires_database_fetch": true,
    "high_cpu_usage": true,
    "template_count": 3000  // Module-specific metadata
  }
}
```

---

## Best Practices & Anti-Patterns

### ✅ Best Practices

**1. Graceful Shutdown**

```go
// TEMPLATE PATTERN: Signal Handling
func (s *Scanner) setupSignalHandling() {
    c := make(chan os.Signal, 1)
    signal.Notify(c, os.Interrupt, syscall.SIGTERM)
    
    go func() {
        <-c
        s.logger.Info("🛑 Received shutdown signal, initiating graceful shutdown...")
        
        // Cancel context (stops ongoing operations)
        s.cancel()
        
        // Cleanup resources
        if s.redisClient != nil {
            s.redisClient.Close()
        }
        
        os.Exit(0)
    }()
}
```

**2. Comprehensive Logging**

```go
// Use structured logging with context
s.logger.Infof("🎯 Starting scan: job_id=%s, domains=%d, mode=%s", 
    s.config.JobID, len(s.config.Domains), s.config.Mode)

// Log errors with stack traces
if err != nil {
    s.logger.Errorf("❌ Scan failed: %v (domain: %s, job_id: %s)", 
        err, domain, s.config.JobID)
}
```

**3. Idempotency**

```sql
-- Use ON CONFLICT for safe retries
INSERT INTO subdomains (subdomain, asset_id, parent_domain, scan_job_id)
VALUES ($1, $2, $3, $4)
ON CONFLICT (subdomain, asset_id) DO UPDATE
SET last_checked = NOW(), scan_job_id = EXCLUDED.scan_job_id;
```

**4. Resource Cleanup**

```go
defer func() {
    if s.redisClient != nil {
        s.redisClient.Close()
    }
    if s.cancel != nil {
        s.cancel()
    }
}()
```

**5. Timeout Enforcement**

```go
ctx, cancel := context.WithTimeout(
    context.Background(), 
    time.Duration(config.Timeout)*time.Minute,
)
defer cancel()

// Check context in loops
for _, domain := range domains {
    select {
    case <-ctx.Done():
        return fmt.Errorf("scan timeout exceeded")
    default:
        // Continue processing
    }
}
```

### ❌ Anti-Patterns

**1. Hardcoded Configuration**

```go
// ❌ BAD: Hardcoded
redisHost := "cache.amazonaws.com"

// ✅ GOOD: Environment variable
redisHost := os.Getenv("REDIS_HOST")
if redisHost == "" {
    redisHost = "localhost"  // Fallback for dev
}
```

**2. Ignoring Errors**

```go
// ❌ BAD: Silent failure
result, _ := scanDomain(domain)

// ✅ GOOD: Proper error handling
result, err := scanDomain(domain)
if err != nil {
    logger.Errorf("Scan failed for %s: %v", domain, err)
    continue  // Or return, depending on severity
}
```

**3. Unbounded Resource Usage**

```go
// ❌ BAD: No limits
for _, domain := range domains {
    go scanDomain(domain)  // Could spawn thousands of goroutines
}

// ✅ GOOD: Worker pool with semaphore
semaphore := make(chan struct{}, maxWorkers)
for _, domain := range domains {
    semaphore <- struct{}{}  // Block if max workers reached
    go func(d string) {
        defer func() { <-semaphore }()
        scanDomain(d)
    }(domain)
}
```

**4. Missing Completion Markers**

```go
// ❌ BAD: Consumer never knows when to stop
for {
    messages := readFromStream()
    process(messages)
    // Infinite loop!
}

// ✅ GOOD: Check for completion
for {
    messages := readFromStream()
    for _, msg := range messages {
        if msg.Type == "completion" {
            return nil  // Exit cleanly
        }
        process(msg)
    }
}
```

**5. Tight Coupling to Infrastructure**

```go
// ❌ BAD: AWS-specific code in scanner logic
func scanDomain(domain string) {
    s3Client := s3.New(session.Must(session.NewSession()))
    s3Client.PutObject(...)  // Directly depends on S3
}

// ✅ GOOD: Abstract storage interface
type ResultStore interface {
    Store(results []Result) error
}

func scanDomain(domain string, store ResultStore) {
    results := performScan(domain)
    store.Store(results)  // Storage implementation can vary
}
```

---

**Document Version**: 1.0  
**Last Updated**: November 19, 2025  
**Previous**: [← Architecture Overview](01-ARCHITECTURE-OVERVIEW.md) | **Next**: [Module Implementation Guide →](03-IMPLEMENTING-A-MODULE.md)
