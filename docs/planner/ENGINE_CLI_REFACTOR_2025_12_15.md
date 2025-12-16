# 🔧 NeoBot-Net CLI Engine Implementation

**Document Created**: December 15, 2025  
**Last Updated**: December 15, 2025  
**Status**: 🟡 In Progress

---

## 📋 Overview

Implementation of a local CLI tool for operator-driven reconnaissance scans. The CLI triggers scans from the terminal while the actual orchestration runs inside AWS VPC with Redis access.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LOCAL TERMINAL                    AWS VPC                       │
│  ──────────────                    ───────                       │
│                                                                  │
│  neobotnet scan run program        ┌──────────────────────────┐ │
│       │                            │  ORCHESTRATOR CONTAINER   │ │
│       │ aws ecs run-task           │                          │ │
│       └───────────────────────────▶│  • scan_pipeline.py      │ │
│                                    │  • Redis access ✅        │ │
│                                    │  • Launches containers    │ │
│                                    └───────────┬──────────────┘ │
│                                                │                 │
│                                                ▼                 │
│                                    ┌──────────────────────────┐ │
│                                    │  SCAN CONTAINERS         │ │
│                                    │  Subfinder → Redis       │ │
│                                    │  DNSx + HTTPx (parallel) │ │
│                                    │  Katana (sequential)     │ │
│                                    └──────────────────────────┘ │
│                                                │                 │
│                                                ▼                 │
│                                           Supabase               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Goals

1. **CLI Tool**: Local command-line interface for triggering scans
2. **Orchestrator Container**: Runs scan pipeline inside VPC with Redis access
3. **Preserve Streaming**: Keep existing Redis streaming architecture
4. **Minimal New Code**: Reuse existing `scan_pipeline.py` and related services

---

## 🔑 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestrator base | Existing backend container | Faster, all dependencies included |
| Program creation | Auto-create if not exists | Convenience for operator |
| Domain input | CLI args + file support | Flexibility for bulk imports |
| Logging | Minimal (rely on scanner logs) | Avoid duplication |
| CLI framework | Typer | Modern, type hints, auto-docs |

---

## 📁 File Structure

```
cli/
├── neobotnet/                      # Local CLI package
│   ├── __init__.py
│   ├── main.py                     # CLI entry point
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── scan.py                 # Scan commands
│   │   └── programs.py             # Program CRUD commands
│   └── config.py                   # AWS/Supabase configuration
├── orchestrator/                   # Runs in AWS VPC
│   ├── Dockerfile
│   ├── main.py                     # Orchestrator wrapper
│   └── requirements.txt
├── pyproject.toml                  # Package configuration
└── README.md                       # CLI documentation
```

---

## ✅ Implementation Tasks

### Phase 1: Orchestrator Container

| Task | Status | Notes |
|------|--------|-------|
| 1.1 Create `cli/orchestrator/main.py` | ✅ Done | Wrapper for scan_pipeline |
| 1.2 Create `cli/orchestrator/Dockerfile` | ✅ Done | Based on backend container |
| 1.3 Create `cli/orchestrator/requirements.txt` | ✅ Done | Minimal deps |
| 1.4 Add Terraform: ECR repository | ✅ Done | For orchestrator image |
| 1.5 Add Terraform: ECS task definition | ✅ Done | Orchestrator task |
| 1.6 Apply Terraform | ⬜ Pending | Create AWS resources |
| 1.7 Build & push container | ⬜ Pending | Deploy to ECR |

### Phase 2: Local CLI Tool

| Task | Status | Notes |
|------|--------|-------|
| 2.1 Create CLI package structure | ✅ Done | neobotnet/ folder |
| 2.2 Create `cli/neobotnet/config.py` | ✅ Done | AWS/Supabase config |
| 2.3 Create `cli/neobotnet/main.py` | ✅ Done | Typer app entry |
| 2.4 Implement `scan run` command | ✅ Done | Core functionality |
| 2.5 Implement `scan status` command | ✅ Done | Check scan progress |
| 2.6 Implement `programs list` command | ✅ Done | List programs |
| 2.7 Implement `programs add` command | ✅ Done | Add program + domains |
| 2.8 Create `pyproject.toml` | ✅ Done | Package config |
| 2.9 Create CLI README | ✅ Done | Usage documentation |

### Phase 3: Testing & Integration

| Task | Status | Notes |
|------|--------|-------|
| 3.1 Install CLI locally | ⬜ Pending | pip install -e . |
| 3.2 Test `programs` commands | ⬜ Pending | CRUD operations |
| 3.3 Test `scan run` command | ⬜ Pending | End-to-end scan |
| 3.4 Verify streaming pipeline | ⬜ Pending | Redis + parallel consumers |
| 3.5 Update project planner | ⬜ Pending | Mark Phase 3 complete |

---

## 📊 Code Reuse Analysis

| Component | Status | Lines |
|-----------|--------|-------|
| `scan_pipeline.py` | ✅ REUSE | 0 new |
| `batch_workflow_orchestrator.py` | ✅ REUSE | 0 new |
| `stream_coordinator.py` | ✅ REUSE | 0 new |
| Scan containers | ✅ REUSE | 0 new |
| Supabase/Redis clients | ✅ REUSE | 0 new |
| **Orchestrator wrapper** | 🆕 CREATE | ~80 lines |
| **Orchestrator Dockerfile** | 🆕 CREATE | ~15 lines |
| **CLI commands** | 🆕 CREATE | ~200 lines |
| **CLI config** | 🆕 CREATE | ~40 lines |
| **Terraform additions** | 🆕 CREATE | ~60 lines |

**Total new code: ~400 lines**

---

## 🔧 Configuration

### Environment Variables (CLI)

```bash
# AWS credentials (for ecs:RunTask)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# ECS configuration
ECS_CLUSTER=neobotnet-v2-dev-cluster
ECS_ORCHESTRATOR_TASK=neobotnet-v2-dev-orchestrator

# Supabase (for programs CRUD)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Network configuration
ECS_SUBNETS=subnet-xxx,subnet-yyy
ECS_SECURITY_GROUP=sg-xxx
```

### Environment Variables (Orchestrator Container)

```bash
# Injected by ECS task definition
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
REDIS_HOST=...
AWS_REGION=...
ECS_CLUSTER=...

# Passed at runtime via overrides
PROGRAM_NAME=...
DOMAINS=...
MODULES=...
```

---

## 📝 Session Notes

### December 15, 2025 - Planning Session

**Decisions Made:**
- Build orchestrator on existing backend container
- Auto-create programs if they don't exist
- Support domain input from CLI args and files
- Minimal logging (rely on existing scanner logs)
- Use Typer for CLI framework

**Next Steps:**
- Create orchestrator container
- Add Terraform for ECR + task definition
- Create CLI package
- Test end-to-end

---

## 📚 References

- [Main Refactor Plan](./REFACTOR_NEO_2025_12_14.md)
- [Scan Pipeline Code](../../backend/app/services/scan_pipeline.py)
- [Batch Orchestrator](../../backend/app/services/batch_workflow_orchestrator.py)
- [Stream Coordinator](../../backend/app/services/stream_coordinator.py)

