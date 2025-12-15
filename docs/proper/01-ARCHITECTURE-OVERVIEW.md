# Architecture Overview

**NeoBot-Net v2 - Template-Based Reconnaissance Framework**

---

## Table of Contents

1. [Introduction](#introduction)
2. [Design Philosophy](#design-philosophy)
3. [System Architecture](#system-architecture)
4. [Data Model & Hierarchy](#data-model--hierarchy)
5. [Component Architecture](#component-architecture)
6. [Execution Modes](#execution-modes)
7. [Technology Stack](#technology-stack)
8. [Security Model](#security-model)
9. [Cost & Performance](#cost--performance)
10. [Architectural Decisions](#architectural-decisions)

---

## Introduction

NeoBot-Net v2 is a **distributed, template-based reconnaissance framework** designed for asset-level security scanning and bug bounty hunting. The system prioritizes:

- **Template-Driven Extensibility**: Zero-code module addition via database configuration
- **Cost Efficiency**: ~$0.01 per scan through intelligent batching and resource allocation
- **Real-Time Streaming**: Redis Streams enable parallel execution and immediate results
- **Production Hardening**: Battle-tested patterns from ProjectDiscovery tools (Subfinder, DNSx, HTTPx)

### Target Use Cases
- **Bug Bounty Programs**: Multi-asset reconnaissance for vulnerability discovery
- **Attack Surface Management**: Continuous monitoring of organizational domains
- **Security Assessments**: Rapid enumeration and probing of external infrastructure

### Key Metrics (Production)
- **Throughput**: 500+ subdomains/minute (Subfinder → DNSx → HTTPx pipeline)
- **Latency**: <2s API response (async execution)
- **Cost**: $18-21/month base + $0.01/scan
- **Scalability**: Tested with 1000+ domains per asset

---

## Design Philosophy

### 1. Database as Single Source of Truth

**Problem**: Hardcoded module configurations scattered across services create maintenance burden and deployment friction.

**Solution**: `scan_module_profiles` table stores all module metadata. Services query this at startup, eliminating code changes for new modules.

**Benefit**: Add new reconnaissance tools (e.g., Nuclei, Nmap) by inserting database rows—no backend deployment required.

```
Deployment Model:
  Traditional: Code Change → Review → Deploy → Restart Services (30+ min)
  Template: Database Insert → Auto-Discovery (< 1 min)
```

### 2. Convention Over Configuration

**Principle**: Intelligent defaults based on common patterns, explicit configuration only when needed.

**Examples**:
- Modules with dependencies automatically enable `requires_database_fetch` flag
- DNSx auto-included when Subfinder requested (persistence requirement)
- Resource scaling computed from domain count without manual specification

**Code Reference**: `backend/app/services/module_registry.py:180-210`

### 3. Container Isolation

**Each module is a standalone Go binary in its own container**, enabling:

- **Independent Scaling**: Subfinder can scale to 4096 CPU while DNSx uses 512 CPU
- **Fault Isolation**: Module crashes don't impact orchestration layer
- **Technology Diversity**: Mix Go, Python, Rust modules seamlessly
- **Rapid Iteration**: Update modules without backend deployment

### 4. Streaming-First Architecture

**Traditional sequential execution** (Module 1 → Wait → Module 2 → Wait → Module 3) wastes time.

**Streaming architecture** (Module 1 → Stream → Module 2 + Module 3 in parallel) maximizes throughput:

```
Sequential Pipeline:
  Subfinder (3min) → DNSx (5min) → HTTPx (4min) = 12 minutes total

Streaming Pipeline:
  Subfinder (3min) → {DNSx + HTTPx in parallel} = 6 minutes total (50% faster)
```

**Trade-off**: Added complexity in consumer group management and completion detection.

---

## System Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER LAYER                                  │
├─────────────────────────────────────────────────────────────────────┤
│  Next.js Frontend (Vercel)                                          │
│    ├─ Dashboard (Asset Management)                                  │
│    ├─ Scan Triggers (Module Selection)                              │
│    └─ Real-Time Results (WebSocket)                                 │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTPS (JWT Auth)
┌────────────────────────▼────────────────────────────────────────────┐
│                     API GATEWAY LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│  FastAPI Backend (AWS ECS Fargate)                                  │
│    ├─ /api/v1/scans (Unified Scan Endpoint)                         │
│    ├─ /api/v1/assets (Asset Management)                             │
│    ├─ /api/v1/usage (Cost Tracking)                                 │
│    └─ /ws (WebSocket for Real-Time Updates)                         │
└────────┬────────────────────────────────┬───────────────────────────┘
         │                                │
         │ (Query/Insert)                 │ (Task Launch)
         │                                │
┌────────▼────────────────┐     ┌─────────▼──────────────────────────┐
│  PERSISTENCE LAYER      │     │   ORCHESTRATION LAYER              │
├─────────────────────────┤     ├────────────────────────────────────┤
│  Supabase (PostgreSQL)  │     │  ScanOrchestrator                  │
│    ├─ assets            │     │    ├─ Asset Validation             │
│    ├─ apex_domains      │     │    ├─ Module Discovery             │
│    ├─ subdomains        │     │    └─ Scan Record Creation         │
│    ├─ dns_records       │     │                                    │
│    ├─ http_probes       │     │  ScanPipeline                      │
│    ├─ scan_jobs         │     │    ├─ Dependency Resolution        │
│    └─ scan_module_      │     │    ├─ Execution Ordering           │
│       profiles          │     │    └─ Module Chaining              │
└─────────────────────────┘     │                                    │
                                │  BatchWorkflowOrchestrator         │
                                │    ├─ Resource Calculator           │
                                │    ├─ Batch Optimizer               │
                                │    └─ ECS Task Launcher             │
                                └─────────┬──────────────────────────┘
                                          │
                                          │ (Launch ECS Tasks)
                                          │
┌─────────────────────────────────────────▼───────────────────────────┐
│                    EXECUTION LAYER (AWS ECS Fargate)                │
├─────────────────────────────────────────────────────────────────────┤
│  Module Containers (Go Binaries)                                    │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐           │
│  │  Subfinder   │──▶│    DNSx      │──▶│    HTTPx     │           │
│  │  (Producer)  │   │  (Consumer)  │   │  (Consumer)  │           │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘           │
│         │                  │                   │                    │
│         │ (XADD)           │ (XADD)           │ (XADD)             │
│         │                  │                   │                    │
│         ▼                  ▼                   ▼                    │
│  ┌──────────────────────────────────────────────────────┐          │
│  │        Redis Streams (ElastiCache)                   │          │
│  │  scan:*:subfinder:output → scan:*:dnsx:output →    │          │
│  │  scan:*:httpx:output                                 │          │
│  └──────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow Summary

1. **User** triggers scan via Next.js frontend
2. **FastAPI** validates request, queries `scan_module_profiles`
3. **ScanPipeline** resolves dependencies (e.g., Subfinder → DNSx → HTTPx)
4. **BatchWorkflowOrchestrator** calculates resources, launches ECS tasks
5. **Module Containers** execute scans:
   - **Subfinder** discovers subdomains → streams to Redis
   - **DNSx** consumes subdomain stream → resolves DNS → writes to database
   - **HTTPx** consumes DNS records → probes HTTP → writes to database
6. **WebSocket** pushes real-time updates to frontend via Redis Pub/Sub

---

## Data Model & Hierarchy

### Entity-Relationship Diagram

```
┌─────────────┐
│    users    │
│  (Supabase) │
└──────┬──────┘
       │ 1:N
       │
┌──────▼──────┐
│   assets    │  (Top-level entity: "EpicGames", "Uber")
│             │  - name, description, bug_bounty_url
└──────┬──────┘  - priority (1-5), tags, is_active
       │ 1:N
       │
┌──────▼──────────┐
│  apex_domains   │  (Root domains: "epicgames.com")
│                 │  - domain (unique), is_active
└──────┬──────────┘  - registrar, dns_servers, last_scanned_at
       │ 1:N
       │
┌──────▼──────────┐
│   subdomains    │  (Discovered: "store.epicgames.com")
│                 │  - subdomain, parent_domain
└─────────────────┘  - source_module, discovered_at, scan_job_id
       │
       ├── 1:N ────▶ dns_records (A, AAAA, CNAME, MX, etc.)
       │
       └── 1:N ────▶ http_probes (status_code, title, technologies)
```

### Core Tables

#### `assets`
**Purpose**: Organizational grouping of reconnaissance targets

```sql
CREATE TABLE assets (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  name TEXT NOT NULL,                    -- "EpicGames", "Uber"
  description TEXT,
  bug_bounty_url TEXT,                   -- HackerOne/Bugcrowd program URL
  priority INTEGER CHECK (priority BETWEEN 1 AND 5),
  is_active BOOLEAN DEFAULT true,
  tags TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes**:
- `idx_assets_user_id` - Fast user asset queries
- `idx_assets_priority` - Priority-based scanning

#### `apex_domains`
**Purpose**: Root domains belonging to an asset

```sql
CREATE TABLE apex_domains (
  id UUID PRIMARY KEY,
  asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
  domain TEXT NOT NULL,                  -- "epicgames.com"
  is_active BOOLEAN DEFAULT true,
  last_scanned_at TIMESTAMPTZ,
  registrar TEXT,
  dns_servers TEXT[],
  metadata JSONB DEFAULT '{}',
  CONSTRAINT valid_domain CHECK (domain ~ '^[a-zA-Z0-9]...')
);
```

**Indexes**:
- `idx_apex_domains_asset_id` - Asset → domains lookup
- `idx_apex_domains_domain` - Unique domain constraint

#### `subdomains`
**Purpose**: Discovered subdomains during reconnaissance

```sql
CREATE TABLE subdomains (
  id UUID PRIMARY KEY,
  scan_job_id UUID NOT NULL,
  asset_id UUID REFERENCES assets(id),
  subdomain TEXT NOT NULL,               -- "store.epicgames.com"
  parent_domain TEXT NOT NULL,           -- "epicgames.com"
  source_module TEXT DEFAULT 'subfinder',
  discovered_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes**:
- `idx_subdomains_asset_id` - Asset-level subdomain queries
- `idx_subdomains_scan_job_id` - Scan result retrieval
- `idx_subdomains_subdomain_unique` - Deduplication

#### `scan_module_profiles`
**Purpose**: Template definitions for scan modules (CRITICAL TABLE)

```sql
CREATE TABLE scan_module_profiles (
  id UUID PRIMARY KEY,
  module_name TEXT NOT NULL UNIQUE,      -- "subfinder", "dnsx", "httpx"
  version TEXT DEFAULT '1.0',
  supports_batching BOOLEAN DEFAULT false,
  max_batch_size INTEGER DEFAULT 1,
  resource_scaling JSONB NOT NULL,       -- CPU/memory scaling rules
  estimated_duration_per_domain INTEGER, -- Seconds
  task_definition_template TEXT NOT NULL,-- ECS task ARN template
  container_name TEXT NOT NULL,          -- "subfinder-scanner"
  dependencies TEXT[] DEFAULT '{}',      -- ["subfinder"] for DNSx
  optimization_hints JSONB DEFAULT '{}', -- Custom module flags
  is_active BOOLEAN DEFAULT true
);
```

**Example Row** (Subfinder):
```json
{
  "module_name": "subfinder",
  "supports_batching": true,
  "max_batch_size": 200,
  "resource_scaling": {
    "domain_count_ranges": [
      {"min_domains": 1, "max_domains": 10, "cpu": 256, "memory": 512},
      {"min_domains": 11, "max_domains": 50, "cpu": 512, "memory": 1024},
      {"min_domains": 51, "max_domains": 200, "cpu": 1024, "memory": 2048}
    ]
  },
  "dependencies": [],
  "optimization_hints": {
    "requires_database_fetch": false,
    "requires_asset_id": true
  }
}
```

---

## Component Architecture

### Backend Services (`backend/app/services/`)

#### **ModuleRegistry** (`module_registry.py`)
**Responsibility**: Module discovery and validation

**Key Methods**:
- `discover_modules()` - Query `scan_module_profiles`, build in-memory cache
- `get_module(module_name)` - Retrieve profile with auto-configuration
- `validate_batch_request()` - Check module capabilities for batching

**Caching Strategy**: 15-minute TTL, refresh on cache miss

**Convention Logic** (Lines 180-210):
```python
# Auto-enable database fetch for modules with dependencies
if module.dependencies and not module.optimization_hints.get('requires_database_fetch'):
    module.optimization_hints['requires_database_fetch'] = True
    logger.info(f"Auto-enabled database fetch for {module_name}")
```

#### **ModuleConfigLoader** (`module_config_loader.py`)
**Responsibility**: Startup-time module configuration loading

**Singleton Pattern**: Global `_module_config` instance

**API**:
```python
config = get_module_config()
dependencies = config.get_dependencies('httpx')  # Returns ['subfinder', 'dnsx']
container = config.get_container_name('dnsx')    # Returns 'dnsx-scanner'
```

**Why Separate from ModuleRegistry?**: Registry handles runtime queries with caching, ConfigLoader provides fast startup-time lookups for pipeline execution.

#### **ScanOrchestrator** (`scan_orchestrator.py`)
**Responsibility**: High-level scan lifecycle management

**Phases**:
1. **Validation**: Asset existence, domain count, module availability
2. **Preparation**: Scan record creation, metadata storage
3. **Execution**: Delegate to ScanPipeline or BatchWorkflowOrchestrator
4. **Monitoring**: Status updates, error handling

**Execution Decision Logic**:
```python
if len(modules) > 1 and has_dependencies(modules):
    # Use pipeline for sequential execution (dependencies)
    await scan_pipeline.execute_pipeline(...)
else:
    # Use direct orchestrator for single modules
    await batch_workflow_orchestrator.execute_scan(...)
```

#### **ScanPipeline** (`scan_pipeline.py`)
**Responsibility**: Dependency resolution and sequential execution

**Key Algorithm**: Topological sort via DFS

```python
def _resolve_execution_order(self, modules: List[str]) -> List[str]:
    """
    Input: ["httpx", "subfinder", "dnsx"]
    Output: ["subfinder", "dnsx", "httpx"]  # Dependency order
    
    Auto-includes DNSx when Subfinder present (persistence requirement)
    """
    ordered = []
    visited = set()
    
    def visit(module):
        if module in visited:
            return
        deps = get_module_config().get_dependencies(module)
        for dep in deps:
            visit(dep)  # Recurse
        visited.add(module)
        ordered.append(module)
    
    for module in modules:
        visit(module)
    return ordered
```

**Timeout Handling**: Per-module timeouts (Subfinder: 10min, DNSx: 30min, HTTPx: 15min)

**Auto-Inclusion Pattern** (Lines 136-145):
```python
if "subfinder" in modules and "dnsx" not in modules:
    logger.info("Auto-including DNSx for Subfinder persistence")
    modules.add("dnsx")
```

#### **BatchWorkflowOrchestrator** (`batch_workflow_orchestrator.py`)
**Responsibility**: ECS task execution with resource optimization

**Sub-Components**:
- **ResourceCalculator**: Computes CPU/memory from domain count
- **BatchOptimizer**: Groups domains for cost efficiency
- **BatchExecutionService**: Launches ECS tasks via boto3

**ECS Task Launch Pattern**:
```python
response = ecs_client.run_task(
    cluster='neobotnet-v2-dev-cluster',
    taskDefinition=module_profile.task_definition_template,
    launchType='FARGATE',
    platformVersion='LATEST',
    networkConfiguration={...},
    overrides={
        'containerOverrides': [{
            'name': container_name,
            'environment': [
                {'name': 'SCAN_JOB_ID', 'value': scan_job_id},
                {'name': 'DOMAINS', 'value': json.dumps(domains)},
                {'name': 'STREAMING_MODE', 'value': 'true'},
                {'name': 'STREAM_OUTPUT_KEY', 'value': f'scan:{scan_job_id}:{module}:output'}
            ],
            'cpu': allocated_cpu,
            'memory': allocated_memory
        }]
    }
)
```

#### **WebSocketManager** (`websocket_manager.py`)
**Responsibility**: Real-time updates to frontend

**Redis Pub/Sub Integration**:
```python
# Module publishes to Redis
await redis.publish(f'scan:{scan_id}:updates', json.dumps({
    'type': 'progress',
    'subdomains_found': 42,
    'module': 'subfinder'
}))

# WebSocketManager subscribes and forwards to connected clients
async for message in pubsub.listen():
    await websocket.send_json(message)
```

---

## Execution Modes

Modules support **three execution modes** to accommodate different use cases:

### 1. Simple Mode (Testing)

**Use Case**: Local development, manual testing, single-domain scans

**Trigger**: No `BATCH_MODE` or `STREAMING_MODE` environment variables

**Configuration**:
```bash
SCAN_JOB_ID=test-123
USER_ID=user-456
DOMAINS='["example.com", "test.com"]'
SUPABASE_URL=https://project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx
```

**Execution Flow**:
1. Parse domains from `DOMAINS` JSON array
2. Execute scan logic synchronously
3. Write results directly to database
4. Exit when complete

**Module Code Reference** (`backend/containers/dnsx-go/main.go:94-192`):
```go
func runSimpleMode() error {
    var domains []string
    json.Unmarshal([]byte(os.Getenv("DOMAINS")), &domains)
    
    dnsxClient, _ := initializeDNSXClient()
    allRecords, _ := resolveDomains(domains, dnsxClient)
    
    supabaseClient, _ := NewSupabaseClient()
    supabaseClient.BulkInsertDNSRecords(allRecords)
    
    return nil
}
```

### 2. Batch Mode (Database Fetch)

**Use Case**: Large domain sets (100+), dependent modules needing upstream data

**Trigger**: `BATCH_MODE=true`

**Configuration**:
```bash
BATCH_MODE=true
BATCH_ID=batch-789
ASSET_ID=asset-abc
BATCH_OFFSET=0
BATCH_LIMIT=200
```

**Execution Flow**:
1. Query database for domains (e.g., DNSx fetches subdomains from previous Subfinder scan)
2. Process in batches with progress tracking
3. Write results to database with batch_scan_id linkage
4. Update batch status in `batch_scan_jobs` table

**Module Code Reference** (`backend/containers/dnsx-go/main.go:194-250`):
```go
func runBatchMode() error {
    batchConfig, _ := loadBatchConfig()  // Queries database
    
    // Fetch domains from database
    domains := fetchDomainsFromDatabase(
        batchConfig.AssetID, 
        batchConfig.BatchOffset, 
        batchConfig.BatchLimit
    )
    
    // Process with progress updates
    for _, domain := range domains {
        records := resolveDomain(domain)
        supabaseClient.InsertDNSRecords(records)
        updateBatchProgress(batchConfig.BatchID, completed++)
    }
    
    return nil
}
```

**Why Needed**: DNSx/HTTPx need to process results from Subfinder. Batch mode enables database pagination for large result sets.

### 3. Streaming Mode (Producer-Consumer)

**Use Case**: Real-time processing, parallel execution, high throughput

**Trigger**: `STREAMING_MODE=true`

**Configuration**:
```bash
STREAMING_MODE=true
STREAM_INPUT_KEY=scan:job-123:subfinder:output   # For consumers
STREAM_OUTPUT_KEY=scan:job-123:dnsx:output       # For producers
CONSUMER_GROUP_NAME=dnsx-consumers
CONSUMER_NAME=dnsx-task-xyz
REDIS_HOST=cache.amazonaws.com
REDIS_PORT=6379
```

**Producer Pattern** (Subfinder):
```go
// TEMPLATE PATTERN: Streaming Producer
func streamSubdomainsToRedis(subdomains []Subdomain) error {
    for _, subdomain := range subdomains {
        // Serialize to JSON
        data, _ := json.Marshal(subdomain)
        
        // XADD to Redis Stream
        redisClient.XAdd(ctx, &redis.XAddArgs{
            Stream: streamOutputKey,
            Values: map[string]interface{}{
                "subdomain": subdomain.Subdomain,
                "source": subdomain.Source,
                "discovered_at": subdomain.DiscoveredAt,
                "parent_domain": subdomain.ParentDomain,
                "asset_id": subdomain.AssetID,
            },
        })
    }
    
    // Send completion marker
    sendCompletionMarker(totalSubdomains)
    return nil
}
```

**Consumer Pattern** (DNSx):
```go
// TEMPLATE PATTERN: Streaming Consumer
func consumeStream(redisClient *redis.Client, config *StreamingConfig) error {
    for {
        // XREADGROUP with consumer group
        streams, _ := redisClient.XReadGroup(ctx, &redis.XReadGroupArgs{
            Group:    config.ConsumerGroupName,
            Consumer: config.ConsumerName,
            Streams:  []string{config.StreamInputKey, ">"},
            Count:    50,  // Batch size
            Block:    5 * time.Second,
        }).Result()
        
        if len(streams) == 0 {
            continue  // No new messages
        }
        
        for _, message := range streams[0].Messages {
            subdomain := parseSubdomain(message.Values)
            
            // Process subdomain
            dnsRecords := resolveDNS(subdomain.Subdomain)
            
            // Write to database
            supabaseClient.InsertDNSRecords(dnsRecords)
            
            // Acknowledge message
            redisClient.XAck(ctx, config.StreamInputKey, 
                config.ConsumerGroupName, message.ID)
        }
        
        // Check for completion marker
        if completionMarkerReceived() {
            break
        }
    }
    return nil
}
```

**Completion Detection**: Producer sends special message `{"type": "completion", "total_results": N}`. Consumer exits loop when received.

---

## Technology Stack

### Backend (Python 3.11+)

**Framework**: FastAPI 0.104+
- **Why FastAPI**: Async support, automatic OpenAPI docs, Pydantic validation
- **Alternative Considered**: Flask (rejected: no native async)

**Key Libraries**:
- `supabase-py` - Database client
- `redis-py` - Cache and streaming
- `boto3` - AWS ECS/CloudWatch integration
- `pydantic` - Request/response validation

**Deployment**: AWS ECS Fargate (512 CPU, 1024 MB memory)

### Modules (Go 1.21+)

**Why Go**:
- **Performance**: 10x faster than Python for I/O-heavy operations
- **Concurrency**: Native goroutines for parallel processing
- **Ecosystem**: ProjectDiscovery SDKs (subfinder, dnsx, httpx) are Go-native

**Standard Library Usage**:
- `encoding/json` - Data serialization
- `context` - Timeout and cancellation
- `os/signal` - Graceful shutdown

**External Dependencies**:
- `github.com/projectdiscovery/subfinder/v2` - Subdomain enumeration
- `github.com/projectdiscovery/dnsx` - DNS resolution
- `github.com/projectdiscovery/httpx` - HTTP probing
- `github.com/go-redis/redis/v8` - Redis Streams

**Deployment**: AWS ECS Fargate (256-4096 CPU, 512-8192 MB memory - dynamically allocated)

### Database (PostgreSQL 15 via Supabase)

**Schema Management**: SQL migrations in `supabase/migrations/`

**Key Indexes**:
```sql
-- Asset lookup optimization
CREATE INDEX idx_subdomains_asset_id ON subdomains(asset_id);
CREATE INDEX idx_dns_records_subdomain_id ON dns_records(subdomain_id);

-- Scan result retrieval
CREATE INDEX idx_subdomains_scan_job_id ON subdomains(scan_job_id);

-- Deduplication
CREATE UNIQUE INDEX idx_subdomains_unique ON subdomains(subdomain, asset_id);
```

**RLS (Row-Level Security)**: Enabled for multi-tenant isolation
```sql
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can only access their assets"
  ON assets FOR ALL
  USING (user_id = auth.uid());
```

### Caching & Streaming (Redis 7.0)

**AWS ElastiCache Configuration**:
- **Instance**: cache.t3.micro (shared.nano in dev)
- **Memory**: 512 MB (sufficient for 1000+ concurrent scans)
- **Persistence**: AOF enabled (durability for scan state)

**Usage Patterns**:
1. **Streams**: Producer-consumer data flow (`XADD`, `XREADGROUP`)
2. **Pub/Sub**: Real-time WebSocket updates
3. **Cache**: Module profile caching (15min TTL)
4. **Job Tracking**: Scan progress state

**Key Expiration**: 24-hour TTL on scan streams (cleanup)

### Container Orchestration (AWS ECS Fargate)

**Cluster**: `neobotnet-v2-dev-cluster`

**Task Definitions** (Managed via Terraform):
- `neobotnet-v2-dev-subfinder`
- `neobotnet-v2-dev-dnsx`
- `neobotnet-v2-dev-httpx`

**Networking**:
- **VPC**: Private subnets with NAT Gateway
- **Security Groups**: Egress-only (no inbound except health checks)

**Cost Model**: Pay-per-use (no idle costs)
```
Subfinder Task: 0.25 vCPU * $0.04048/hour * 0.05 hours = $0.00051
DNSx Task: 0.25 vCPU * $0.04048/hour * 0.083 hours = $0.00084
Total per scan: ~$0.01 (including memory and network)
```

### Frontend (Next.js 14 + TypeScript)

**Deployment**: Vercel (Edge network for global latency <100ms)

**Key Libraries**:
- `shadcn/ui` - Component library
- `tanstack/react-query` - API state management
- `zustand` - Client state
- `socket.io-client` - WebSocket integration

**Build Optimization**: 
- Static page generation for dashboards
- Dynamic imports for heavy components
- Webpack bundle splitting (<200KB initial load)

---

## Security Model

### Authentication & Authorization

**User Authentication**: Supabase Auth (JWT tokens)

**API Security**:
```python
# backend/app/core/dependencies.py
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    user_id = payload.get("sub")
    # Verify user in database
    return user_id
```

**Row-Level Security**: PostgreSQL RLS policies ensure users only access their own data

### Container Security

**Principle of Least Privilege**:
- Module containers have read-only filesystem (except `/tmp`)
- No shell access (`USER nonroot` in Dockerfile)
- Secrets via environment variables (not files)

**IAM Roles**:
```hcl
# ECS Task Role (minimum permissions)
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

**Network Isolation**: Private subnets, egress-only security groups

### Secrets Management

**Storage**: AWS Secrets Manager

**Access Pattern**:
```python
# Backend reads secrets at startup
secrets_client = boto3.client('secretsmanager')
supabase_key = secrets_client.get_secret_value(
    SecretId='neobotnet-v2/supabase-service-key'
)['SecretString']
```

**Rotation**: Automatic 90-day rotation for Supabase keys

### Input Validation

**Domain Validation** (Database constraint):
```sql
CONSTRAINT valid_domain CHECK (
  domain ~ '^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
)
```

**API Validation** (Pydantic models):
```python
class AssetScanRequest(BaseModel):
    asset_id: UUID
    modules: List[str] = Field(min_items=1, max_items=10)
    active_domains_only: bool = True
```

---

## Cost & Performance

### Cost Breakdown (Monthly)

**Base Infrastructure**:
```
Supabase (Free Tier):           $0
Redis (cache.t3.micro):         $13
ECS Backend (always-on):        $8
Total Base:                     $21/month
```

**Per-Scan Variable Costs**:
```
Subfinder (3 min, 256 CPU, 512 MB):   $0.003
DNSx (5 min, 512 CPU, 1024 MB):       $0.006
HTTPx (4 min, 512 CPU, 1024 MB):      $0.005
Data Transfer (negligible):           $0.001
Total per Full Scan:                  $0.015 (~$0.01 rounded)
```

**Scaling Economics**:
- 100 scans/month: $22/month
- 500 scans/month: $28/month
- 1000 scans/month: $36/month

### Performance Characteristics

**API Latency** (p50/p95/p99):
- Scan trigger: 150ms / 300ms / 500ms (async, non-blocking)
- Asset retrieval: 80ms / 150ms / 250ms
- Subdomain query: 120ms / 250ms / 400ms

**Scan Throughput**:
- Subfinder: 10-50 subdomains/second (API rate limits)
- DNSx: 100-500 DNS queries/second
- HTTPx: 20-100 HTTP probes/second

**Resource Utilization**:
- Backend: ~60% CPU, ~400MB memory (idle)
- Subfinder container: ~40% CPU, ~250MB memory (active scan)
- DNSx container: ~70% CPU, ~600MB memory (active scan)

### Scalability Limits

**Current Architecture Supports**:
- 10,000+ assets per user
- 100,000+ subdomains per asset
- 50 concurrent scans per user
- 500 concurrent scans globally

**Bottlenecks**:
1. **ECS Task Limit**: 500 tasks per account (soft limit, can increase)
2. **Redis Memory**: 512MB = ~10,000 pending stream messages
3. **Database Connections**: Supabase Pro = 500 connections

**Mitigation Strategies**:
- Batch optimization reduces task count by 80%
- Stream TTL prevents memory accumulation
- Connection pooling (max 20 per backend instance)

---

## Architectural Decisions

### ADR-001: Database-Driven Module Configuration

**Decision**: Store module metadata in `scan_module_profiles` table

**Context**: Hardcoded module configurations scattered across 7 service files

**Alternatives**:
- YAML configuration files (rejected: requires deployment)
- Environment variables (rejected: not type-safe)
- Code-based configuration (rejected: high coupling)

**Consequences**:
- ✅ Zero-code module addition
- ✅ Single source of truth
- ⚠️ Database migration required for schema changes

### ADR-002: Go for Module Containers

**Decision**: Implement scan modules in Go

**Context**: Python subprocess-based approach too slow (10x overhead)

**Alternatives**:
- Python with asyncio (rejected: ProjectDiscovery SDKs are Go)
- Rust (rejected: smaller ecosystem, steeper learning curve)

**Consequences**:
- ✅ 10x performance improvement
- ✅ Native SDK integration
- ⚠️ Requires Go expertise

### ADR-003: Redis Streams Over Message Queues

**Decision**: Use Redis Streams for module communication

**Context**: Need real-time producer-consumer data flow

**Alternatives**:
- SQS (rejected: not real-time, higher latency)
- RabbitMQ (rejected: additional infrastructure cost)
- Direct database polling (rejected: too slow)

**Consequences**:
- ✅ Sub-second latency
- ✅ Consumer groups for parallel processing
- ⚠️ Requires Redis operational expertise

### ADR-004: ECS Fargate Over EC2/Lambda

**Decision**: Run modules on ECS Fargate

**Context**: Need container orchestration with per-second billing

**Alternatives**:
- Lambda (rejected: 15min timeout, cold starts)
- EC2 Auto Scaling (rejected: idle costs, slower scaling)
- Kubernetes (rejected: operational overhead)

**Consequences**:
- ✅ No idle costs
- ✅ Fast scaling (30s to launch)
- ⚠️ Higher per-minute cost than EC2

### ADR-005: Convention Over Configuration for Dependencies

**Decision**: Auto-enable flags based on module dependencies

**Context**: Manual configuration error-prone (Bug #7: DNSx missing database fetch)

**Alternatives**:
- Strict manual configuration (rejected: brittle)
- Fail-fast on missing config (rejected: poor UX)

**Consequences**:
- ✅ 90% of modules need zero configuration
- ✅ Self-healing system (auto-includes DNSx with Subfinder)
- ⚠️ "Magic" behavior requires documentation

---

**Document Version**: 1.0  
**Last Updated**: November 19, 2025  
**Next**: [Module System Deep Dive →](02-MODULE-SYSTEM.md)
