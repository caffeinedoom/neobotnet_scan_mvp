# Katana Module - Testing Guide

This document provides comprehensive testing information for the Katana web crawler module.

---

## 📊 Test Coverage Summary

| Package | Coverage | Tests | Status |
|---------|----------|-------|--------|
| `internal/dedup` | **100%** | 11 tests, 3 benchmarks | ✅ Passing |
| `internal/config` | **44.2%** | 20 tests | ✅ Passing |
| `internal/database` | 0% | - | ⏳ Integration tests pending |
| `internal/scanner` | 0% | - | ⏳ Integration tests pending |
| `internal/models` | N/A | - | Data structures only |

**Overall:** 31 unit tests passing, 100% coverage on critical deduplication logic

---

## 🧪 Running Tests

### Run All Tests
```bash
cd backend/containers/katana-go
go test ./internal/...
```

### Run Tests with Coverage
```bash
go test -cover ./internal/...
```

### Run Specific Package
```bash
go test -v ./internal/dedup/    # URL normalization tests
go test -v ./internal/config/   # Configuration tests
```

### Run Benchmarks
```bash
go test -bench=. -benchmem ./internal/dedup/
```

### Generate HTML Coverage Report
```bash
go test -coverprofile=coverage.out ./internal/...
go tool cover -html=coverage.out -o coverage.html
```

---

## 📝 Test Categories

### 1. Unit Tests ✅

#### **Deduplication Tests** (`internal/dedup/dedup_test.go`)
Tests URL normalization and SHA256 hashing logic critical for endpoint deduplication.

**Test Cases:**
- ✅ Lowercase scheme and host
- ✅ Remove fragments (`#section`)
- ✅ Sort query parameters alphabetically
- ✅ Remove trailing slashes (except root `/`)
- ✅ Remove default ports (`:80`, `:443`)
- ✅ Keep non-default ports
- ✅ Handle complex URLs with all features
- ✅ Handle special characters in query strings
- ✅ Error handling for invalid URLs
- ✅ Deduplication (identical URLs → same hash)
- ✅ Hash consistency (same input → same output)

**Benchmarks:**
```
BenchmarkNormalizeURL       390,212 ops/sec    2.89 μs/op    928 B/op
BenchmarkHashURL          3,976,700 ops/sec    281 ns/op     192 B/op
BenchmarkNormalizeAndHash   455,090 ops/sec    2.63 μs/op  1,120 B/op
```

#### **Config Tests** (`internal/config/config_test.go`)
Tests environment variable parsing, validation, and execution mode selection.

**Test Cases:**
- ✅ Simple mode configuration loading
- ✅ Batch mode configuration loading
- ✅ Streaming mode configuration loading
- ✅ Missing required fields validation
- ✅ Crawl depth validation (0-5 range)
- ✅ Concurrency validation (1-50 range)
- ✅ Strategy validation (`depth-first` | `breadth-first`)
- ✅ Integer environment variable parsing
- ✅ Boolean environment variable parsing (`true`, `1`, `yes`)
- ✅ Default value handling

---

### 2. Integration Tests ⏳ (Pending)

Integration tests require external dependencies (Supabase, Redis, Chromium) and are best run in a containerized environment.

#### **Planned Integration Tests:**

1. **Database Integration**
   - Supabase client connectivity
   - Repository CRUD operations
   - ON CONFLICT upsert logic
   - Seed URL fetching from `http_probes`
   - Scan job status tracking

2. **Scanner Integration**
   - Katana hybrid engine initialization
   - Headless crawling with Chromium
   - Result capture via OnResult callback
   - Source URL tracking
   - Error handling for failed crawls

3. **Redis Streams** (Phase 5)
   - Consumer group creation
   - Message consumption (XREAD)
   - Message acknowledgment (XACK)
   - Producer output stream

---

### 3. End-to-End Tests ⏳ (Pending)

E2E tests validate the complete workflow from configuration to database storage.

#### **Planned E2E Tests:**

1. **Simple Mode E2E**
   - Parse config from environment
   - Initialize scanner
   - Crawl single URL
   - Store results in database
   - Verify deduplication

2. **Batch Mode E2E**
   - Fetch seed URLs from `http_probes`
   - Crawl multiple URLs
   - Batch upsert to database
   - Verify `times_discovered` increment

3. **Error Handling E2E**
   - Invalid configuration
   - Database connection failure
   - Crawl timeout
   - Graceful shutdown (SIGTERM)

---

## 🎯 Test Data

### Sample URLs for Testing

```go
// Valid test URLs
"https://example.com/"
"https://example.com/api/users?id=123&sort=asc"
"HTTPS://EXAMPLE.COM:443/Path#fragment"

// Invalid test URLs
"://example.com"  // Missing scheme
"not-a-url"       // Invalid format
```

### Environment Variables for Testing

```bash
# Simple Mode
export SCAN_JOB_ID="test-job-123"
export ASSET_ID="test-asset-456"
export USER_ID="test-user-789"
export SUPABASE_URL="https://test.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="test-key"
export TARGET_URLS="https://example.com,https://test.com"

# Batch Mode
export BATCH_MODE="true"
export BATCH_ID="batch-001"
export BATCH_OFFSET="0"
export BATCH_LIMIT="20"

# Streaming Mode
export STREAMING_MODE="true"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export STREAM_INPUT_KEY="scan:httpx:results"
export CONSUMER_GROUP="katana-workers"
export CONSUMER_NAME="worker-1"
```

---

## 🐛 Debugging Tests

### Enable Verbose Output
```bash
go test -v ./internal/dedup/
```

### Run Single Test
```bash
go test -v -run TestNormalizeURL ./internal/dedup/
```

### Run with Race Detector
```bash
go test -race ./internal/...
```

### Show Failed Tests Only
```bash
go test ./internal/... | grep FAIL
```

---

## 📈 Performance Benchmarks

### Deduplication Performance

Based on benchmarks, the module can process:

- **URL Normalization**: ~390,000 URLs/second
- **SHA256 Hashing**: ~3,976,000 hashes/second
- **Combined (Normalize + Hash)**: ~455,000 URLs/second

**Memory Usage (per operation):**
- Normalize: 928 bytes, 17 allocations
- Hash: 192 bytes, 3 allocations
- Combined: 1,120 bytes, 20 allocations

**Production Estimates:**
- 10,000 URLs: ~22ms processing time
- 100,000 URLs: ~220ms processing time
- 1,000,000 URLs: ~2.2s processing time

---

## ✅ Test Checklist

### Unit Tests (Completed ✅)
- [x] URL normalization logic
- [x] SHA256 hashing
- [x] Deduplication consistency
- [x] Config parsing (simple mode)
- [x] Config parsing (batch mode)
- [x] Config parsing (streaming mode)
- [x] Config validation
- [x] Environment variable parsing

### Integration Tests (Pending ⏳)
- [ ] Supabase client connectivity
- [ ] Repository CRUD operations
- [ ] Scanner initialization
- [ ] Headless crawling
- [ ] Redis Streams (Phase 5)

### E2E Tests (Pending ⏳)
- [ ] Simple mode workflow
- [ ] Batch mode workflow
- [ ] Error handling scenarios
- [ ] Graceful shutdown

---

## 🔧 Testing Tools & Dependencies

- **Go Testing Framework**: Native `go test`
- **Coverage Tool**: `go tool cover`
- **Benchmarking**: `go test -bench`
- **Race Detector**: `go test -race`

No external testing libraries required for unit tests!

---

## 📚 Next Steps

1. **Integration Tests** (Phase 6.2)
   - Set up Supabase test instance
   - Create database fixtures
   - Test repository operations
   - Validate ON CONFLICT logic

2. **E2E Tests** (Phase 6.3)
   - Dockerize test environment
   - Create test seed data
   - Run full workflows
   - Validate database state

3. **Performance Tests** (Phase 6.4)
   - Test with 100+ URLs
   - Monitor memory usage
   - Validate deduplication
   - Measure insert throughput

---

## 📊 Test Metrics

**Current Status:**
- ✅ 31 unit tests passing (100%)
- ✅ 100% coverage on deduplication logic
- ✅ 44% coverage on config parsing
- ✅ 3 benchmarks for performance validation
- ⏳ Integration tests pending
- ⏳ E2E tests pending

**Goal:**
- 80%+ code coverage overall
- All critical paths tested
- Performance benchmarks documented
- E2E workflows validated

---

**Last Updated:** November 24, 2025  
**Test Status:** Phase 6.1 Complete (Unit Tests) ✅

