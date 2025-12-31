# Pipeline Robustness Implementation Plan

**Created**: December 30, 2025  
**Updated**: December 31, 2025  
**Status**: ✅ Layers 1 & 3 Complete, Layer 2 Pending  
**Estimated Effort**: ~4 hours total

### Progress
- ✅ Layer 1: Increase Default Timeout + CLI Flag (Completed)
- ⏳ Layer 2: Activity-Based Idle Detection (Pending - lower priority)
- ✅ Layer 3: Graceful Completion Guarantees (Completed)

---

## Executive Summary

The scan pipeline's 1-hour fixed timeout was causing premature termination for large targets with many subdomains (e.g., 800+ historical URLs). This plan implements a **3-layer robustness improvement** to ensure scans complete reliably regardless of target size.

### Problem Statement
- Fixed 1-hour timeout was too short for large targets
- HTTPx and URL-Resolver stayed in "pending" status past timeout
- Orchestrator reported "timeout" even though containers were still processing
- No way to configure timeout per-scan

### Solution Architecture
```
┌──────────────────────────────────────────────────────────────────────────┐
│                      3-LAYER ROBUSTNESS ARCHITECTURE                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  LAYER 1: Configurable Timeout (COMPLETED ✅)                            │
│  ├── Default: 3 hours (up from 1 hour)                                   │
│  ├── CLI: --timeout flag (30m to 24h)                                    │
│  └── Pass-through: CLI → Orchestrator → ScanPipeline                     │
│                                                                          │
│  LAYER 2: Activity-Based Idle Detection (PENDING ⏳)                      │
│  ├── Track "last_activity_at" for each batch_scan_job                    │
│  ├── Idle timeout: 30 min with no status change → timeout                │
│  └── Dynamic: Adapts to actual processing time                           │
│                                                                          │
│  LAYER 3: Graceful Completion Guarantees (PENDING ⏳)                     │
│  ├── Ensure all consumers update batch_scan_job.status to "completed"    │
│  ├── Add retry logic for database status updates                         │
│  └── Container shutdown hook to mark "completed" even on exit            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Configurable Timeout (COMPLETED ✅)

**Effort**: 30 minutes  
**Status**: ✅ Deployed

### Changes Made

| File | Change |
|------|--------|
| `backend/app/services/scan_pipeline.py` | Added `DEFAULT_PIPELINE_TIMEOUT = 10800` (3h), added `timeout_seconds` param |
| `cli/neobotnet/commands/scan.py` | Added `--timeout` flag with validation (30m-24h) |
| `cli/orchestrator/main.py` | Reads `PIPELINE_TIMEOUT` env var, passes to pipeline |

### Usage

```bash
# Default: 3 hours
neobotnet scan run "T-Mobile" --modules "subfinder,dnsx,httpx" --scale 5

# Custom: 6 hours for very large targets
neobotnet scan run "MegaCorp" --modules "..." --timeout 21600

# Maximum: 24 hours for extreme cases
neobotnet scan run "GoogleVRP" --modules "..." --timeout 86400
```

### Technical Details

1. **CLI** reads `--timeout` (default 10800s) and passes as `PIPELINE_TIMEOUT` env var
2. **Orchestrator** reads env var and passes `timeout_seconds` to `run_scan_pipeline()`
3. **ScanPipeline.execute_pipeline()** uses `timeout_seconds` in `_wait_for_jobs_completion()`
4. Timeout is logged at start: `⏱️ Pipeline timeout set to: 3h 0m (10800s)`

---

## Layer 2: Activity-Based Idle Detection (PENDING)

**Effort**: 2 hours  
**Status**: ⏳ Not Started  
**Priority**: Medium

### Problem
Fixed timeouts (even 3 hours) may be:
- Too long for small targets (wasted wait time)
- Too short for very large targets (still premature timeout)

### Solution
Instead of a fixed timeout, detect "idle" conditions - if no module makes progress for N minutes, then timeout.

### Implementation Plan

#### Phase 2.1: Track Last Activity (30 min)

Add `last_activity_at` column to `batch_scan_jobs` table:

```sql
ALTER TABLE batch_scan_jobs 
ADD COLUMN last_activity_at TIMESTAMPTZ DEFAULT NOW();

-- Index for efficient queries
CREATE INDEX idx_batch_scan_jobs_last_activity 
ON batch_scan_jobs (last_activity_at) 
WHERE status IN ('pending', 'running');
```

#### Phase 2.2: Update Activity Timestamp (30 min)

Modify each container to update `last_activity_at` on:
- Processing a batch of items
- Publishing to Redis stream
- Any meaningful progress

```go
// In each container's processing loop
func (s *Scanner) updateActivityTimestamp() error {
    return s.supabase.UpdateBatchScanJob(s.batchID, map[string]interface{}{
        "last_activity_at": time.Now().UTC().Format(time.RFC3339),
    })
}
```

#### Phase 2.3: Implement Idle Detection (45 min)

Modify `_wait_for_jobs_completion()` in `scan_pipeline.py`:

```python
async def _wait_for_jobs_completion(
    self,
    job_ids: List[str],
    timeout: int = 10800,           # Max total timeout
    idle_timeout: int = 1800,       # 30 min idle timeout
    check_interval: int = 10
) -> Dict[str, Any]:
    
    last_activity = datetime.utcnow()
    
    while True:
        # ... existing status check ...
        
        # Check for activity
        jobs = self.supabase.table("batch_scan_jobs")...
        
        newest_activity = max(job["last_activity_at"] for job in jobs.data)
        
        if newest_activity > last_activity:
            last_activity = newest_activity
            self.logger.info(f"📊 Activity detected at {newest_activity}")
        
        # Idle timeout check
        idle_seconds = (datetime.utcnow() - last_activity).total_seconds()
        if idle_seconds > idle_timeout:
            self.logger.warning(f"⚠️ Idle timeout: no activity for {idle_seconds}s")
            return {"status": "idle_timeout", ...}
```

#### Phase 2.4: Testing (15 min)

Test scenarios:
- [ ] Small target completes quickly (no idle timeout)
- [ ] Large target takes >1h but stays active (no timeout)
- [ ] Stuck container triggers idle timeout

### Files to Modify
- `backend/app/services/scan_pipeline.py`
- `backend/containers/*/supabase.go` (activity updates)
- Supabase migration for new column

---

## Layer 3: Graceful Completion Guarantees (COMPLETED ✅)

**Effort**: 1.5 hours  
**Status**: ✅ Completed (Dec 31, 2025)  
**Priority**: High

### Problem
Some containers don't properly update their `batch_scan_job.status` to "completed":
- HTTPx logs showed `BATCH_ID not set, skipping status update`
- URL-Resolver stayed in "pending" after processing data

### Root Cause Analysis
1. **Missing BATCH_ID**: Some code paths don't receive BATCH_ID env var
2. **Silent failures**: Status update failures are logged but not retried
3. **No shutdown hook**: If container exits unexpectedly, status isn't updated

### Solution
Guarantee that every container updates its status before exiting.

### Implementation Plan

#### Phase 3.1: Audit BATCH_ID Propagation (30 min)

Verify BATCH_ID is passed in all execution paths:

| Path | BATCH_ID Set? | Fix Needed? |
|------|---------------|-------------|
| `_build_container_environment()` | ✅ Yes | No |
| `_build_streaming_consumer_environment()` | ✅ Yes (via parent) | Verify |
| Container override in ECS | ✅ Yes | Verify |

Check each container's status update code:
- [ ] subfinder-go: Line 351-355
- [ ] dnsx-go: Check streaming.go
- [ ] httpx-go: Line 116-127 (has BATCH_ID check)
- [ ] katana-go: Line 289-298
- [ ] waymore-go: Check main.go
- [ ] url-resolver: Check streaming.go

#### Phase 3.2: Add Status Update Retry (30 min)

Wrap status updates with retry logic:

```go
func (s *SupabaseClient) UpdateBatchScanStatusWithRetry(
    batchID string, 
    status string, 
    metadata map[string]interface{},
    maxRetries int,
) error {
    var lastErr error
    for attempt := 1; attempt <= maxRetries; attempt++ {
        err := s.UpdateBatchScanStatus(batchID, status, metadata)
        if err == nil {
            return nil
        }
        lastErr = err
        log.Printf("⚠️ Status update failed (attempt %d/%d): %v", 
            attempt, maxRetries, err)
        time.Sleep(time.Duration(attempt) * time.Second) // Exponential backoff
    }
    return fmt.Errorf("status update failed after %d retries: %w", maxRetries, lastErr)
}
```

#### Phase 3.3: Add Shutdown Hook (30 min)

Ensure containers update status even on SIGTERM:

```go
func setupGracefulShutdown(batchID string, supabase *SupabaseClient) {
    sigChan := make(chan os.Signal, 1)
    signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

    go func() {
        sig := <-sigChan
        log.Printf("📛 Received signal: %v, updating status...", sig)
        
        // Best-effort status update
        _ = supabase.UpdateBatchScanStatusWithRetry(batchID, "interrupted", 
            map[string]interface{}{
                "interrupted_at": time.Now().UTC().Format(time.RFC3339),
                "signal": sig.String(),
            }, 3)
        
        os.Exit(130) // Standard exit code for SIGTERM
    }()
}
```

### Files to Modify
- `backend/containers/*/supabase.go` (retry logic)
- `backend/containers/*/main.go` (shutdown hook)
- `backend/containers/httpx-go/streaming.go` (verify BATCH_ID)
- `backend/containers/url-resolver/streaming.go` (verify BATCH_ID)

---

## Testing Plan

### Layer 1 Testing (Ready Now)
- [x] CLI accepts `--timeout` flag
- [x] Orchestrator logs timeout at start
- [x] Pipeline uses provided timeout
- [ ] Run T-Mobile scan with 3h timeout → verify completion

### Layer 2 Testing (After Implementation)
- [ ] Idle detection triggers after 30 min of no activity
- [ ] Active scan doesn't trigger idle timeout
- [ ] `last_activity_at` updates correctly

### Layer 3 Testing (After Implementation)
- [ ] All containers update status to "completed"
- [ ] Status update retries on failure
- [ ] SIGTERM triggers graceful shutdown with status update

---

## Rollout Plan

1. **Layer 1** (DONE): Deploy immediately, re-run T-Mobile scan
2. **Layer 2**: Implement after Layer 1 proves stable (1-2 days)
3. **Layer 3**: Implement in parallel with Layer 2 (overlapping)

---

## Metrics to Track

After implementation, monitor:
- Timeout rate (should decrease)
- Scan completion rate (should increase)
- Average scan duration vs. domain count
- Idle timeout triggers (should be rare)

