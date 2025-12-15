# 🔄 NeoBot-Net LEAN Refactoring Plan

**Document Created**: December 14, 2025  
**Last Updated**: December 14, 2025  
**Status**: 🟡 Planning Phase

---

## 📋 Table of Contents

1. [Goal Statement](#goal-statement)
2. [Current Architecture](#current-architecture)
3. [Desired Architecture](#desired-architecture)
4. [Key Decisions](#key-decisions)
5. [Phase Overview](#phase-overview)
6. [Detailed Tasks](#detailed-tasks)
7. [File Inventory](#file-inventory)
8. [Database Changes](#database-changes)
9. [Risk Assessment](#risk-assessment)
10. [Progress Tracking](#progress-tracking)

---

## 🎯 Goal Statement

Transform NeoBot-Net from a **complex multi-tenant SaaS platform** into a **lean, CLI-driven reconnaissance data service** with:

- **Preserved scan engine** - The streaming pipeline (Subfinder → DNSx + HTTPx → Katana) remains the core
- **CLI-driven operations** - Operator triggers scans from terminal, not API
- **Google SSO authentication** - Simple auth barrier for access control
- **Custom API keys** - Users get API keys for programmatic access
- **Public data model** - All authenticated users access ALL reconnaissance data
- **Minimal UI** - Programs list, data browser, API docs only
- **Cost-efficient infrastructure** - Remove always-on backend, keep scan containers

### Success Criteria

- [ ] CLI can trigger full scan pipeline (Subfinder → DNSx + HTTPx → Katana)
- [ ] Users can sign in with Google SSO
- [ ] Users receive custom API key after sign-in
- [ ] API provides read-only access to all recon data
- [ ] Simple UI displays programs and data
- [ ] Monthly infrastructure cost reduced from ~$44 to ~$13
- [ ] Scan pipeline executes correctly with streaming architecture

---

## 🏗️ Current Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CURRENT ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐      ┌──────────────────────────────────────────┐     │
│  │   Frontend   │      │            Backend (Always-On)           │     │
│  │  (Next.js)   │─────▶│  FastAPI on ECS Fargate                  │     │
│  │              │      │  • Auth service (JWT, sessions)          │     │
│  │  • Dashboard │      │  • Asset service (CRUD)                  │     │
│  │  • Auth UI   │      │  • Scan orchestrator (API trigger)       │     │
│  │  • Scan mgmt │      │  • Usage/quota tracking                  │     │
│  │  • WebSocket │      │  • WebSocket real-time                   │     │
│  └──────────────┘      └─────────────────┬────────────────────────┘     │
│                                          │                               │
│                                          ▼                               │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │                    SCAN PIPELINE (ECS Tasks)                   │      │
│  │                                                                │      │
│  │  Subfinder ──▶ Redis Stream ──▶ DNSx ──▶ Supabase            │      │
│  │     (Go)           │                (Go)                      │      │
│  │                    └──────────▶ HTTPx ──▶ Supabase            │      │
│  │                                   (Go)                        │      │
│  │                                                                │      │
│  │  (Katana exists but not integrated into pipeline)            │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐     │
│  │  Supabase      │  │  Redis         │  │  AWS Infrastructure    │     │
│  │  (PostgreSQL)  │  │  (ElastiCache) │  │  • ALB (~$16/mo)       │     │
│  │  • Multi-tenant│  │  • Streams     │  │  • ECS Backend (~$15)  │     │
│  │  • RLS by user │  │  • Pub/Sub     │  │  • CloudFront          │     │
│  │  • User quotas │  │                │  │  • Route53             │     │
│  └────────────────┘  └────────────────┘  └────────────────────────┘     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Current Components

| Layer | Component | Purpose | Monthly Cost |
|-------|-----------|---------|--------------|
| Frontend | Next.js Dashboard | Full user management, scan UI | $0 (Vercel) |
| Backend | FastAPI on ECS | API, auth, orchestration | ~$15 |
| Load Balancer | AWS ALB | Route traffic, health checks | ~$16 |
| Database | Supabase | Multi-tenant data, auth | $0 (free tier) |
| Cache | Redis ElastiCache | Streaming, pub/sub | ~$13 |
| CDN | CloudFront | SSL termination, caching | ~$0 |
| Scan Containers | ECS Fargate Tasks | Subfinder, DNSx, HTTPx, Katana | ~$0.015/scan |
| **Total Base** | | | **~$44/month** |

### Current Problems

1. **Over-engineered for validation** - Complex multi-tenant system before proving market fit
2. **High fixed costs** - Always-on backend even with no users
3. **API-triggered scans** - Requires full backend to be running
4. **Complex auth flows** - More than needed for simple access control
5. **Katana not integrated** - Fourth scan module exists but not in pipeline
6. **User-owned assets** - Complexity for feature we may not need

---

## 🎯 Desired Architecture

### Target System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DESIRED ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      RESEARCHER (User)                            │   │
│  │                                                                   │   │
│  │  1. Visit site ──▶ "Sign in with Google"                         │   │
│  │  2. Receive custom API key                                        │   │
│  │  3. Access ALL recon data (subdomains, DNS, probes)              │   │
│  │  4. Use simple UI or API                                          │   │
│  └─────────────────────────────────┬────────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  ┌──────────────┐      ┌────────────────────────────────────────────┐   │
│  │   Frontend   │      │         Backend (Serverless/Minimal)       │   │
│  │  (Next.js)   │─────▶│                                            │   │
│  │              │      │  FastAPI (Vercel or minimal ECS)           │   │
│  │  • Landing   │      │  • Auth: Google SSO only                   │   │
│  │  • Programs  │      │  • API keys: Generate/validate             │   │
│  │  • Data view │      │  • Read-only public data endpoints         │   │
│  │  • API docs  │      │  • No scan triggering (CLI only)           │   │
│  └──────────────┘      └────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      OPERATOR (You)                               │   │
│  │                                                                   │   │
│  │  CLI: ./neobotnet scan hackerone.com                             │   │
│  │                                                                   │   │
│  │  1. Add programs via CLI                                          │   │
│  │  2. Trigger scans via CLI                                         │   │
│  │  3. Pipeline executes on ECS                                      │   │
│  │  4. Results stored in Supabase                                    │   │
│  │  5. All authenticated users can read                              │   │
│  └─────────────────────────────────┬────────────────────────────────┘   │
│                                    │                                     │
│                                    ▼                                     │
│  ┌───────────────────────────────────────────────────────────────┐      │
│  │              SCAN PIPELINE (ECS Tasks - On Demand)             │      │
│  │                                                                │      │
│  │  Subfinder ──▶ Redis Stream ─┬──▶ DNSx ──▶ Supabase           │      │
│  │     (Go)                     │       (Go)    │                │      │
│  │                              └──▶ HTTPx ──┬──┘                │      │
│  │                                    (Go)   │                   │      │
│  │                                           ▼                   │      │
│  │                                       Katana ──▶ Supabase     │      │
│  │                                         (Go)                  │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                                                                          │
│  ┌────────────────┐  ┌────────────────┐                                 │
│  │  Supabase      │  │  Redis         │                                 │
│  │  (PostgreSQL)  │  │  (ElastiCache) │                                 │
│  │  • Public read │  │  • Streams     │                                 │
│  │  • Auth only   │  │                │                                 │
│  │  • API keys    │  │                │                                 │
│  └────────────────┘  └────────────────┘                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Target Cost Structure

| Component | Purpose | Monthly Cost |
|-----------|---------|--------------|
| Frontend | Simple landing + data browser | $0 (Vercel) |
| Backend | Minimal API (or Supabase Edge Functions) | $0-5 |
| Database | Supabase (auth + data) | $0 (free tier) |
| Redis | Streaming for scan pipeline | ~$13 |
| Scan Containers | On-demand ECS tasks | ~$0.015/scan |
| **Total Base** | | **~$13/month** |

**Savings: ~$31/month (70% reduction)**

---

## 🔑 Key Decisions

### Confirmed Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Authentication | Google SSO via Supabase | Simple, prevents spam, reuses code |
| API Keys | Custom keys (not JWT) | Better UX for developers |
| Data Access | All authenticated users see ALL data | Simple model, no per-user isolation |
| Scan Trigger | CLI only (no UI trigger) | Operator control, no always-on backend |
| Rate Limiting | None initially | Simplify MVP, add later if needed |
| Data Export | Not allowed initially | Keep users on platform, add later |
| Last Scan Date | Show in UI and API | Transparency, data freshness |
| Katana Integration | Sequential after HTTPx | Needs HTTP probes to know what to crawl |

### Scan Pipeline Flow

```
User triggers via CLI
        │
        ▼
┌───────────────┐
│   Subfinder   │  Producer - discovers subdomains
│   (Go)        │  Streams to Redis: scan:{job_id}:subfinder:output
└───────┬───────┘
        │
        ▼ Redis Stream
        │
   ┌────┴────┐
   │         │
   ▼         ▼
┌──────┐  ┌──────┐
│ DNSx │  │HTTPx │  Parallel consumers
│ (Go) │  │ (Go) │  Read from Subfinder stream
└──┬───┘  └──┬───┘  Write to Supabase
   │         │
   └────┬────┘
        │
        ▼ HTTPx completion triggers
        │
┌───────▼───────┐
│    Katana     │  Sequential - web crawling
│    (Go)       │  Reads from http_probes table
└───────────────┘  Writes to crawled_endpoints
```

---

## 📊 Phase Overview

| Phase | Name | Duration | Focus |
|-------|------|----------|-------|
| 1 | Auth Simplification | 1 day | Keep Google SSO, add API keys, remove quotas |
| 2 | Database Refactoring | 0.5 day | Modify RLS, add API keys table, remove user tables |
| 3 | CLI Development | 1.5 days | Create CLI, integrate with scan pipeline |
| 4 | Katana Integration | 1 day | Add Katana to pipeline after HTTPx |
| 5 | API Simplification | 1 day | Read-only endpoints, API key validation |
| 6 | Frontend Simplification | 1 day | Landing page, programs view, API docs |
| 7 | Infrastructure Cleanup | 0.5 day | Remove ALB, update GitHub workflow |
| 8 | Testing & Validation | 0.5 day | End-to-end testing, documentation |

**Total Estimated Duration: 7 days**

---

## ✅ Detailed Tasks

### Phase 1: Auth Simplification
**Duration**: 1 day  
**Goal**: Simplify auth to Google SSO only, add custom API key generation

#### Tasks

- [ ] **1.1** Review and understand current auth flow in `auth_service.py`
- [ ] **1.2** Remove email/password auth (keep Google SSO only)
- [ ] **1.3** Create API keys table schema
  ```sql
  CREATE TABLE api_keys (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
      key_hash TEXT NOT NULL,  -- SHA256 of key
      key_prefix TEXT NOT NULL,  -- First 8 chars for display
      name TEXT DEFAULT 'Default',
      created_at TIMESTAMPTZ DEFAULT NOW(),
      last_used_at TIMESTAMPTZ,
      is_active BOOLEAN DEFAULT true
  );
  ```
- [ ] **1.4** Create API key generation service
- [ ] **1.5** Create API key validation middleware
- [ ] **1.6** Remove usage tracking from auth flows
- [ ] **1.7** Remove quota checks from auth flows
- [ ] **1.8** Test Google SSO still works
- [ ] **1.9** Test API key generation and validation

**Files to Modify**:
- `backend/app/services/auth_service.py` - Simplify
- `backend/app/core/dependencies.py` - Add API key validation
- `backend/app/core/security.py` - Add API key hashing

**Files to Create**:
- `backend/app/services/api_key_service.py`

**Files to Delete**:
- None in this phase

---

### Phase 2: Database Refactoring
**Duration**: 0.5 day  
**Goal**: Modify RLS for public data access, remove unused tables

#### Tasks

- [ ] **2.1** Create migration: Modify RLS policies
  ```sql
  -- Change from "user sees own" to "authenticated sees all"
  DROP POLICY IF EXISTS "Users can view own assets" ON assets;
  CREATE POLICY "Authenticated users see all assets" ON assets
    FOR SELECT USING (auth.role() = 'authenticated');
  
  -- Similar for subdomains, dns_records, http_probes, crawled_endpoints
  ```
- [ ] **2.2** Create migration: Add API keys table
- [ ] **2.3** Create migration: Remove user_id from assets
- [ ] **2.4** Create migration: Add operator-only flags
  ```sql
  ALTER TABLE assets ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT true;
  ALTER TABLE assets ADD COLUMN IF NOT EXISTS created_by_operator BOOLEAN DEFAULT true;
  ```
- [ ] **2.5** Create migration: Drop user_quotas table
- [ ] **2.6** Create migration: Drop user_usage table
- [ ] **2.7** Update bulk insert functions for new schema
- [ ] **2.8** Test all read queries work with new RLS
- [ ] **2.9** Test write queries (should fail for non-service role)

**Migrations to Create**:
- `database/migrations/20251214_01_lean_rls_policies.sql`
- `database/migrations/20251214_02_api_keys_table.sql`
- `database/migrations/20251214_03_remove_user_tables.sql`

---

### Phase 3: CLI Development
**Duration**: 1.5 days  
**Goal**: Create CLI for operator-driven scans

#### Tasks

- [ ] **3.1** Create CLI project structure
  ```
  cli/
  ├── neobotnet/
  │   ├── __init__.py
  │   ├── main.py          # Entry point
  │   ├── commands/
  │   │   ├── __init__.py
  │   │   ├── programs.py  # Add/list programs
  │   │   └── scans.py     # Trigger scans
  │   └── utils/
  │       ├── __init__.py
  │       └── supabase.py  # DB client
  ├── pyproject.toml
  └── README.md
  ```
- [ ] **3.2** Implement `programs add` command
- [ ] **3.3** Implement `programs list` command
- [ ] **3.4** Implement `programs delete` command
- [ ] **3.5** Implement `scan` command (trigger pipeline)
- [ ] **3.6** Integrate with `scan_pipeline.execute_pipeline()`
- [ ] **3.7** Add progress output and logging
- [ ] **3.8** Test CLI locally with mock data
- [ ] **3.9** Test CLI with actual ECS task launching
- [ ] **3.10** Document CLI usage

**Files to Create**:
- `cli/neobotnet/main.py`
- `cli/neobotnet/commands/programs.py`
- `cli/neobotnet/commands/scans.py`
- `cli/pyproject.toml`
- `cli/README.md`

---

### Phase 4: Katana Integration
**Duration**: 1 day  
**Goal**: Add Katana as sequential step after HTTPx completion

#### Tasks

- [ ] **4.1** Review existing Katana container code
- [ ] **4.2** Design Katana trigger mechanism (after HTTPx completes)
- [ ] **4.3** Modify `scan_pipeline.py` to include Katana step
- [ ] **4.4** Create Katana batch job creation logic
- [ ] **4.5** Implement HTTPx → Katana handoff
- [ ] **4.6** Update Katana container to read from http_probes
- [ ] **4.7** Test Katana execution in isolation
- [ ] **4.8** Test full pipeline: Subfinder → DNSx + HTTPx → Katana
- [ ] **4.9** Update monitoring to include Katana status

**Files to Modify**:
- `backend/app/services/scan_pipeline.py`
- `backend/containers/katana-go/` (if needed)

**Files to Create**:
- None (integration into existing)

---

### Phase 5: API Simplification
**Duration**: 1 day  
**Goal**: Create read-only public API with API key auth

#### Tasks

- [ ] **5.1** Create new simplified API router structure
- [ ] **5.2** Implement `GET /api/v1/programs` endpoint
- [ ] **5.3** Implement `GET /api/v1/programs/{id}` endpoint
- [ ] **5.4** Implement `GET /api/v1/programs/{id}/subdomains` endpoint
- [ ] **5.5** Implement `GET /api/v1/programs/{id}/dns` endpoint
- [ ] **5.6** Implement `GET /api/v1/programs/{id}/probes` endpoint
- [ ] **5.7** Implement `GET /api/v1/programs/{id}/endpoints` endpoint
- [ ] **5.8** Implement `GET /api/v1/search` endpoint
- [ ] **5.9** Implement `GET /api/v1/auth/me` endpoint
- [ ] **5.10** Implement `POST /api/v1/auth/api-key` endpoint
- [ ] **5.11** Add API key validation to all endpoints
- [ ] **5.12** Remove old complex endpoints (scans.py, etc.)
- [ ] **5.13** Update main.py with new routers
- [ ] **5.14** Test all endpoints with API key auth

**Files to Create**:
- `backend/app/api/v1/programs.py`
- `backend/app/api/v1/search.py`

**Files to Modify**:
- `backend/app/api/v1/__init__.py`
- `backend/app/main.py`

**Files to Delete**:
- `backend/app/api/v1/scans.py`
- `backend/app/services/scan_orchestrator.py`
- `backend/app/services/usage_service.py`
- `backend/app/services/websocket_manager.py`

---

### Phase 6: Frontend Simplification
**Duration**: 1 day  
**Goal**: Simple landing page with data browser

#### Tasks

- [ ] **6.1** Design simplified page structure
  ```
  app/
  ├── page.tsx              # Landing + sign in
  ├── programs/
  │   ├── page.tsx          # Programs list
  │   └── [id]/page.tsx     # Program detail
  ├── api-docs/
  │   └── page.tsx          # API documentation
  ├── auth/
  │   └── callback/page.tsx # OAuth callback
  └── layout.tsx            # Simplified layout
  ```
- [ ] **6.2** Create landing page component
- [ ] **6.3** Create programs list page
- [ ] **6.4** Create program detail page (subdomains, DNS, probes)
- [ ] **6.5** Create API docs page
- [ ] **6.6** Simplify AuthContext (Google only)
- [ ] **6.7** Add API key display after login
- [ ] **6.8** Add "last scanned" display
- [ ] **6.9** Remove old dashboard, assets, scans pages
- [ ] **6.10** Update global styles for clean design
- [ ] **6.11** Test auth flow end-to-end
- [ ] **6.12** Test data display

**Files to Create**:
- `frontend/src/app/programs/page.tsx`
- `frontend/src/app/programs/[id]/page.tsx`
- `frontend/src/app/api-docs/page.tsx`

**Files to Modify**:
- `frontend/src/app/page.tsx`
- `frontend/src/app/layout.tsx`
- `frontend/src/contexts/AuthContext.tsx`

**Files/Folders to Delete**:
- `frontend/src/app/dashboard/`
- `frontend/src/app/assets/`
- `frontend/src/app/scans/`
- `frontend/src/app/recon/`

---

### Phase 7: Infrastructure Cleanup
**Duration**: 0.5 day  
**Goal**: Remove unnecessary infrastructure, update CI/CD

#### Tasks

- [ ] **7.1** Remove ALB from Terraform
- [ ] **7.2** Remove always-on backend ECS service
- [ ] **7.3** Keep Redis and scan container definitions
- [ ] **7.4** Update CloudFront to point to Vercel (frontend only)
- [ ] **7.5** Update GitHub workflow to build containers only
- [ ] **7.6** Remove backend deployment steps from workflow
- [ ] **7.7** Test container builds work
- [ ] **7.8** Test scan pipeline still executes on ECS

**Files to Modify**:
- `infrastructure/terraform/alb.tf` → DELETE or comment out
- `infrastructure/terraform/ecs-batch-integration.tf` → Remove backend service
- `infrastructure/terraform/cloudfront.tf` → Simplify
- `.github/workflows/deploy-backend-optimized-improved.yml` → Simplify

---

### Phase 8: Testing & Validation
**Duration**: 0.5 day  
**Goal**: End-to-end testing and documentation

#### Tasks

- [ ] **8.1** Test complete user journey (sign in → API key → data access)
- [ ] **8.2** Test CLI scan workflow (add program → trigger scan → verify data)
- [ ] **8.3** Test full scan pipeline execution
- [ ] **8.4** Verify Katana integration works
- [ ] **8.5** Test API endpoints with real data
- [ ] **8.6** Verify cost reduction (check AWS billing)
- [ ] **8.7** Update project README
- [ ] **8.8** Update API documentation
- [ ] **8.9** Archive old code (don't delete, move to `_archived/`)
- [ ] **8.10** Final review and cleanup

---

## 📁 File Inventory

### Files to KEEP (Core Value)

```
backend/app/
├── services/
│   ├── scan_pipeline.py              ✅ Core - streaming orchestration
│   ├── stream_coordinator.py         ✅ Core - Redis Streams
│   ├── batch_workflow_orchestrator.py ✅ Core - ECS task launching
│   ├── batch_execution.py            ✅ Core - batch job execution
│   ├── batch_optimizer.py            ✅ Core - batch optimization
│   ├── batch_monitoring.py           ✅ Core - job monitoring
│   ├── module_registry.py            ✅ Core - module discovery
│   ├── module_config_loader.py       ✅ Core - module config
│   ├── resource_calculator.py        ✅ Core - resource allocation
│   └── dns_service.py                ✅ Utility - DNS queries
├── core/
│   ├── config.py                     ✅ Configuration
│   ├── environment.py                ✅ Environment vars
│   └── supabase_client.py            ✅ Database client
├── schemas/
│   ├── batch.py                      ✅ Batch job schemas
│   ├── dns.py                        ✅ DNS schemas
│   ├── http_probes.py                ✅ HTTP probe schemas
│   └── recon.py                      ✅ Recon module schemas
└── utils/                            ✅ Utilities

backend/containers/
├── subfinder-go/                     ✅ Subdomain discovery
├── dnsx-go/                          ✅ DNS resolution
├── httpx-go/                         ✅ HTTP probing
└── katana-go/                        ✅ Web crawling

infrastructure/terraform/
├── ecs-optimized.tf                  ✅ Container definitions
├── ecs-batch-integration.tf          ✅ Batch IAM (modify to remove service)
├── redis.tf                          ✅ Redis for streaming
├── networking.tf                     ✅ VPC/subnets
├── security.tf                       ✅ Security groups
├── secrets.tf                        ✅ SSM parameters
├── providers.tf                      ✅ AWS provider
├── variables.tf                      ✅ Variables
└── outputs.tf                        ✅ Outputs
```

### Files to MODIFY

```
backend/app/
├── main.py                           ⚙️ Remove complex routers, simplify startup
├── core/
│   ├── dependencies.py               ⚙️ Add API key validation
│   └── security.py                   ⚙️ Add API key hashing
├── services/
│   └── auth_service.py               ⚙️ Simplify to Google SSO + API keys
└── schemas/
    └── assets.py                     ⚙️ Simplify for public model

frontend/src/
├── app/
│   ├── page.tsx                      ⚙️ Simplify to landing
│   └── layout.tsx                    ⚙️ Remove complex auth wrapper
└── contexts/
    └── AuthContext.tsx               ⚙️ Google SSO only

infrastructure/terraform/
├── ecs-batch-integration.tf          ⚙️ Remove backend ECS service
└── cloudfront.tf                     ⚙️ Simplify for frontend only

.github/workflows/
└── deploy-backend-optimized-improved.yml  ⚙️ Container builds only
```

### Files to DELETE

```
backend/app/
├── api/v1/
│   └── scans.py                      ❌ CLI triggers scans
├── services/
│   ├── scan_orchestrator.py          ❌ Replaced by CLI
│   ├── usage_service.py              ❌ No usage tracking
│   ├── websocket_manager.py          ❌ No real-time UI
│   └── asset_service.py              ❌ CLI manages assets
└── schemas/
    └── auth.py                       ❌ Simplify auth

frontend/src/app/
├── dashboard/                        ❌ No user dashboard
├── assets/                           ❌ CLI manages assets
├── scans/                            ❌ CLI triggers scans
└── recon/                            ❌ Merged into programs/

infrastructure/terraform/
└── alb.tf                            ❌ No load balancer needed
```

### Files to CREATE

```
cli/
├── neobotnet/
│   ├── __init__.py
│   ├── main.py
│   └── commands/
│       ├── programs.py
│       └── scans.py
├── pyproject.toml
└── README.md

backend/app/
├── services/
│   └── api_key_service.py            🆕 API key management
└── api/v1/
    ├── programs.py                   🆕 Public data endpoints
    └── search.py                     🆕 Search endpoint

frontend/src/app/
├── programs/
│   ├── page.tsx                      🆕 Programs list
│   └── [id]/page.tsx                 🆕 Program detail
└── api-docs/
    └── page.tsx                      🆕 API documentation

database/migrations/
├── 20251214_01_lean_rls_policies.sql
├── 20251214_02_api_keys_table.sql
└── 20251214_03_remove_user_tables.sql
```

---

## 🗄️ Database Changes

### New Table: api_keys

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL,
    key_prefix TEXT NOT NULL,
    name TEXT DEFAULT 'Default',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_used_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true NOT NULL,
    
    CONSTRAINT unique_key_hash UNIQUE (key_hash)
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);

-- RLS: Users manage their own keys
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own API keys" ON api_keys
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY "Service role full access" ON api_keys
    USING (auth.role() = 'service_role');
```

### Modified RLS Policies

```sql
-- ASSETS: All authenticated users can read
DROP POLICY IF EXISTS "Users can view own assets" ON assets;
CREATE POLICY "Authenticated users read all assets" ON assets
    FOR SELECT USING (auth.role() = 'authenticated');

-- Only service role can write (operator via CLI)
CREATE POLICY "Service role manages assets" ON assets
    FOR ALL USING (auth.role() = 'service_role');

-- Similar pattern for:
-- subdomains, dns_records, http_probes, crawled_endpoints
```

### Tables to DROP

```sql
DROP TABLE IF EXISTS user_quotas CASCADE;
DROP TABLE IF EXISTS user_usage CASCADE;
```

### Columns to Remove

```sql
ALTER TABLE assets DROP COLUMN IF EXISTS user_id;
```

---

## ⚠️ Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Break scan pipeline during refactor | Medium | High | Test pipeline in isolation first |
| Auth changes break existing flow | Low | Medium | Keep Supabase Auth, just simplify |
| RLS changes expose wrong data | Low | High | Test all queries before deploy |
| CLI integration issues | Medium | Medium | Test with mock data first |
| Katana integration complexity | Medium | Medium | Implement as separate phase |
| Cost savings not realized | Low | Low | Monitor AWS billing during rollout |

---

## 📈 Progress Tracking

### Phase Status

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| 1. Auth Simplification | ✅ Completed | Dec 14 | Dec 15 | Google SSO + X SSO + API keys implemented |
| 2. Database Refactoring | ✅ Completed | Dec 15 | Dec 15 | RLS migration created, pending execution |
| 3. CLI Development | ⬜ Not Started | | | Operator CLI for triggering scans |
| 4. Katana Integration | 🟡 Partial | Dec 14 | | Terraform + CI/CD done, pipeline integration pending |
| 5. API Simplification | ✅ Completed | Dec 15 | Dec 15 | /v1/programs endpoints for public read access |
| 6. Frontend Simplification | ✅ Completed | Dec 15 | Dec 15 | Programs page, API docs, landing page, navigation |
| 7. Infrastructure Cleanup | 🟡 Partial | Dec 14 | | New workflow, Katana ECR. Remaining: remove ALB, backend ECS |
| 8. Testing & Validation | ⬜ Not Started | | | End-to-end testing |

### Legend
- ⬜ Not Started
- 🟡 In Progress
- ✅ Completed
- ❌ Blocked

---

## 📝 Session Notes

### December 14, 2025 - Session 1
- Initial planning session
- Confirmed key decisions: Google SSO, custom API keys, no rate limits, no export
- Created comprehensive refactoring plan
- Identified 8 phases with ~7 days total effort

### December 14, 2025 - Session 2 (Phase 1 Complete)
**Completed:**
- ✅ Created `database/migrations/20251214_01_add_api_keys.sql` - API keys table schema
- ✅ Created `backend/app/services/api_key_service.py` - Key generation, validation, management
- ✅ Updated `backend/app/core/dependencies.py` - Added API key auth support alongside JWT
- ✅ Created `frontend/src/lib/supabase.ts` - Supabase client for Google SSO
- ✅ Rewrote `frontend/src/contexts/AuthContext.tsx` - Google SSO + API key management
- ✅ Created `frontend/src/app/auth/callback/page.tsx` - OAuth callback handler
- ✅ Rewrote `backend/app/api/v1/auth.py` - Removed email/password, added API key endpoints
- ✅ Deleted `backend/app/api/v1/usage.py` - No more usage tracking
- ✅ Deleted `backend/app/services/usage_service.py` - No more usage tracking
- ✅ Updated `backend/app/main.py` - Removed usage router

**Note:** Frontend needs `@supabase/supabase-js` package installed:
```bash
cd frontend && pnpm install
```

**Next Step:** Phase 2 - Database Refactoring (RLS policies, remove user tables)

### December 14, 2025 - Session 3 (Infrastructure + CI/CD)
**Completed:**
- ✅ Created `.github/workflows/deploy-lean.yml` - Simplified CI/CD with Katana support
- ✅ Added Katana ECR repository to `infrastructure/terraform/ecs-optimized.tf`
- ✅ Added Katana task definition to Terraform
- ✅ Added Katana outputs to `infrastructure/terraform/outputs.tf`
- ✅ Updated `frontend/package.json` with `@supabase/supabase-js` dependency

**Infrastructure Changes:**
- New GitHub workflow (`deploy-lean.yml`) replaces complex workflow
- Katana container now has ECR repository and ECS task definition
- Scan pipeline: Subfinder → (DNSx + HTTPx) → Katana

**Manual Steps Required:**
1. Run database migration in Supabase SQL Editor:
   ```sql
   -- Run contents of: database/migrations/20251214_01_add_api_keys.sql
   ```

2. Install frontend dependencies:
   ```bash
   cd frontend && pnpm install
   ```

3. Configure environment variables in Vercel:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` (your backend API URL)

4. Enable Google OAuth in Supabase Dashboard:
   - Go to Authentication → Providers → Google
   - Add Google OAuth credentials

5. Deploy infrastructure:
   ```bash
   cd infrastructure/terraform
   terraform init
   terraform plan
   terraform apply
   ```

**Next Step:** Phase 2 - Database Refactoring (RLS policies for public data)

### December 15, 2025 - Session 4 (Frontend Cleanup + Auth Complete)
**Completed:**
- ✅ Fixed frontend build errors (TypeScript, unused imports)
- ✅ Deleted `/scans` page - scans triggered via CLI
- ✅ Deleted `/recon` page - scan forms not needed
- ✅ Deleted `/assets/create` page - assets managed via CLI
- ✅ Deleted `/assets/[id]/edit` page - edit via CLI
- ✅ Deleted `/auth/register` page - Google/X SSO only
- ✅ Deleted `DomainScanForm.tsx`, `ScanHistory.tsx`, `ScanResults.tsx` - scan components
- ✅ Deleted `RegisterForm.tsx` - no registration
- ✅ Rewrote `navigation.tsx` - simplified LEAN navigation
- ✅ Rewrote `LoginForm.tsx` - Google + X SSO buttons only
- ✅ Added X (Twitter) SSO support to `supabase.ts` and `AuthContext.tsx`
- ✅ Fixed `supabase.ts` to handle missing env vars during build

**Frontend Pages Remaining:**
```
/                    - Landing page
/auth/login          - Google + X SSO
/auth/callback       - OAuth redirect
/dashboard           - API keys, user info
/assets              - Browse assets (read-only)
/assets/[id]         - Asset details
/subdomains          - Browse subdomains
/dns                 - Browse DNS records
/probes              - Browse HTTP probes
```

**Files Deleted (2,823 lines removed):**
- `frontend/src/app/scans/page.tsx`
- `frontend/src/app/recon/page.tsx`
- `frontend/src/app/assets/create/page.tsx`
- `frontend/src/app/assets/[id]/edit/page.tsx`
- `frontend/src/app/auth/register/page.tsx`
- `frontend/src/components/recon/DomainScanForm.tsx`
- `frontend/src/components/recon/ScanHistory.tsx`
- `frontend/src/components/recon/ScanResults.tsx`
- `frontend/src/components/auth/RegisterForm.tsx`

**OAuth Configuration Completed:**
- Google SSO working ✓
- X (Twitter) SSO working ✓
- Supabase redirect URLs configured ✓

**Next Steps:**
1. Phase 2: Database Refactoring (RLS policies for public data)
2. Phase 3: CLI Development
3. Phase 6: Frontend - Add programs page and API docs

---

## 📚 References

- [Architecture Overview](../proper/01-ARCHITECTURE-OVERVIEW.md)
- [Module System](../proper/02-MODULE-SYSTEM.md)
- [Data Flow & Streaming](../proper/05-DATA-FLOW-AND-STREAMING.md)
- [Current Schema](../../schema.sql)

