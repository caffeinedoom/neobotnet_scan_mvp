# Phase 3: Container Implementation - Checkpoint

**Date**: 2025-11-14  
**Status**: 🔄 IN PROGRESS (80% complete)  
**Priority**: Streaming Mode (primary use case)

---

## ✅ Completed Components

### 1. **scanner.go** - HTTP Probing Logic ✅
- ✅ Replaced DNS resolution with HTTP probing using httpx SDK
- ✅ Created `HTTPProbe` struct (22 fields matching database schema)
- ✅ Implemented `probeHTTP()` function using `runner.Options`
- ✅ Implemented `convertResultToProbe()` for field mapping (all 14 fields)
- ✅ Added helper functions: `extractParentDomain()`, `parsePort()`, `extractSubdomain()`
- ⚠️ **Minor issue**: Need to verify httpx SDK options compile correctly

### 2. **database.go** - Database Integration ✅
- ✅ Created `HTTPProbeInsertResult` struct
- ✅ Implemented `BulkInsertHTTPProbes()` function
- ✅ Removed DNS-specific code (DNSRecord struct, BulkInsertDNSRecords)
- ✅ Direct INSERT to `http_probes` table (no RPC function needed)

### 3. **go.mod** - Dependencies ✅
- ✅ Updated module name: `dnsx-go` → `httpx-go`
- ✅ Added httpx dependencies:
  - `github.com/projectdiscovery/httpx@v1.7.1`
  - `github.com/projectdiscovery/goflags@v0.1.74`
  - `github.com/projectdiscovery/gologger@v1.1.54`
- ✅ Removed dnsx dependencies
- ✅ Upgraded Go version to 1.24.0 (required by httpx)

---

## 🔄 Partially Complete

### 4. **main.go** - Entry Point ⚠️
**Status**: 60% complete

✅ **Completed:**
- Updated container startup log: "HTTPx HTTP Probe Container"
- Stubbed out `runBatchMode()` (not needed for streaming)

❌ **Remaining:**
- Fix `runSimpleMode()` for local testing:
  - Replace `initializeDNSXClient()` → remove (not needed)
  - Replace `resolveDomains()` → `probeHTTP()`
  - Replace `BulkInsertDNSRecords()` → `BulkInsertHTTPProbes()`
  - Update variable names: `domains` → `subdomains`

### 5. **streaming.go** - Consumer Pattern ⚠️
**Status**: 0% complete (CRITICAL - Primary use case!)

❌ **Needs complete update:**
- Replace DNS resolution logic with HTTP probing
- Update consumer group: `dnsx-consumers` → `httpx-consumers`
- Update Redis stream key pattern: `scan:{scan_job_id}:subfinder:output`
- Replace `processDNSData()` → use `convertResultToProbe()` from scanner.go
- Replace `BulkInsertDNSRecords()` → `BulkInsertHTTPProbes()`

### 6. **Dockerfile** - Container Build ⚠️
**Status**: 0% complete

❌ **Needs update:**
- Change binary name: `dnsx-scanner` → `httpx-scanner`
- Update labels:
  - `module.name=dnsx` → `module.name=httpx`
  - `module.description` → "HTTP probing using ProjectDiscovery httpx"
- Update base image if needed (currently Go 1.23)

---

## 🚧 Compilation Issues

### Current Build Errors:
```
./main.go:134: undefined: initializeDNSXClient
./main.go:140: undefined: resolveDomains  
./streaming.go:76: undefined: initializeDNSXClient
./streaming.go:328: undefined: processDNSData
```

**Root Cause**: runSimpleMode and streaming.go still reference DNS functions

---

## 📋 Next Steps (Priority Order)

### **CRITICAL PATH** (Streaming Mode):
1. **Update streaming.go** (2-3 hours)
   - Replace DNS logic with HTTP probing
   - Test Redis Stream consumption from subfinder
   - Verify bulk insert works

2. **Update Dockerfile** (15 min)
   - Change binary name and labels
   - Build and test image

3. **Integration Test** (1 hour)
   - Test with docker-compose locally
   - Verify subfinder → httpx stream works
   - Check database inserts

### **NICE TO HAVE** (Simple Mode for Testing):
4. **Fix runSimpleMode** (30 min)
   - Replace DNS functions with HTTP probing
   - Test with DOMAINS env var

---

## 🎯 Estimated Remaining Time

- **Critical Path (Streaming)**: 3-4 hours
- **Nice to Have (Simple Mode)**: 0.5 hours
- **Total**: 3.5-4.5 hours

**Phase 3 Original Estimate**: 5-6 hours  
**Time Spent So Far**: ~2 hours  
**Remaining**: ~3.5 hours (within estimate)

---

## 🔍 Key Learnings

1. **HTTPx SDK Options**: Had to map field names correctly:
   - `Title` → `ExtractTitle`
   - `WebServer` → `OutputServerHeader`
   - `CDNName` → `OutputCDN`
   - `FavIconHash` → `Favicon`

2. **Result Struct**: `FaviconMD5` → `FavIconMD5` (typo in my initial code)

3. **Batch Mode**: Not needed immediately (streaming mode is primary use case per user decision)

4. **Direct INSERT**: Unlike dnsx (which uses PostgreSQL RPC function), httpx inserts directly to table

---

## 📝 Files Status Summary

| File | Status | Priority | Notes |
|------|--------|----------|-------|
| scanner.go | ✅ 95% | HIGH | Core logic done, minor fixes needed |
| database.go | ✅ 100% | HIGH | Complete |
| go.mod/go.sum | ✅ 100% | HIGH | Dependencies resolved |
| streaming.go | ❌ 0% | **CRITICAL** | Primary use case - NEEDS WORK |
| Dockerfile | ❌ 0% | HIGH | Simple updates needed |
| main.go | ⚠️ 60% | MEDIUM | Simple mode for testing |
| batch_support.go | ✅ 100% | LOW | Config only, no changes needed |

---

**Next Action**: Update streaming.go to enable HTTPx streaming consumer

