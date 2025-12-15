# Katana Output Analysis - Executive Summary

**Date:** November 20, 2025  
**Status:** ✅ Analysis Complete

---

## Quick Facts

- **Test Duration:** 60 seconds
- **URLs Crawled:** 3 seed URLs (Nubank domains)
- **Endpoints Discovered:** 9 unique endpoints
- **Data Generated:** 2.8 MB JSON output
- **Average Endpoint Size:** ~311 KB (including response body)

---

## Key Findings

### ✅ What We Learned

1. **Clean Output Structure** - Katana produces consistent, well-structured JSON perfect for database storage
2. **Response Bodies Are Large** - HTML responses range from 140KB-280KB, requiring strategic storage
3. **Headers Are Rich** - 20-56 headers per response with valuable metadata (server, content-type, etc.)
4. **Failure Handling** - Failed requests return `null` for status_code and empty headers
5. **Duplicates Exist** - Same URL can be discovered multiple times (need deduplication)

### 📊 Data Distribution

| Content Type | Count | Avg Size |
|--------------|-------|----------|
| `text/html` | 7 | ~250 KB |
| `application/javascript` | 1 | ~5 KB |
| Failed requests | 2 | 0 KB |

### 🏗️ Recommended Database Schema

**Primary Table:** `crawled_endpoints`
- Core metadata (URL, status, content-type, headers)
- JSONB for headers (enables queries like "find all nginx servers")
- Per-scan deduplication using `(scan_job_id, url_hash)`

**Secondary Table:** `endpoint_response_bodies`
- Stores bulky HTML bodies separately
- Keeps main table queries fast
- Allows selective retrieval

**Optional Tables (Future):**
- `detected_technologies` - When Wappalyzer is enabled
- `detected_forms` - For form discovery

---

## Critical Design Decisions

### ✅ Approved for MVP

1. **Per-Scan Deduplication** - Same URL tracked across multiple scans
2. **JSONB Headers** - Flexible, queryable JSON storage
3. **Separate Body Storage** - Performance optimization
4. **Full Body Storage** - For depth ≤ 2 crawls (manageable volume)
5. **URL Normalization** - SHA256 hash of normalized URL

### 🔄 Deferred to Future

1. **Technology Detection** - Not present in current output
2. **Form Discovery** - No forms found in test
3. **Source Tracking** - `source_url` and `discovered_from` fields
4. **Compression** - Can add later for long-term retention
5. **S3 Archival** - For data older than 30 days

---

## Next Steps

### Phase 1: Schema Implementation (This Week)
1. ✅ Create migration SQL for `crawled_endpoints`
2. ✅ Create migration SQL for `endpoint_response_bodies`
3. ✅ Add indexes for common query patterns
4. ⏳ Test schema with sample data

### Phase 2: Go Code Implementation (Next Week)
1. ⏳ Implement URL normalization and hashing
2. ⏳ Parse response headers to extract content-type
3. ⏳ Batch INSERT for performance (100-500 rows per transaction)
4. ⏳ Handle NULL values for failed requests

### Phase 3: Integration Testing (Following Week)
1. ⏳ Run 5-minute test with 10 URLs
2. ⏳ Measure database performance under realistic load
3. ⏳ Verify deduplication and indexing
4. ⏳ Benchmark query performance

---

## Storage Projections

| Scenario | URLs | Depth | Est. Endpoints | Est. Storage |
|----------|------|-------|----------------|--------------|
| **Small Scan** | 10 URLs | 1 | ~100 | ~30 MB |
| **Medium Scan** | 100 URLs | 1 | ~1,000 | ~300 MB |
| **Large Scan** | 100 URLs | 2 | ~10,000+ | ~3 GB |
| **Asset Scan** | 500 URLs | 1 | ~5,000 | ~1.5 GB |

**💡 Conclusion:** Depth-1 crawls are highly manageable for bug bounty recon.

---

## Questions Answered

### ❓ Should we store full HTML bodies?
**✅ Yes** - For depth ≤ 2, storage is manageable (< 1GB per scan). We can optimize later with compression/archival.

### ❓ How should we handle deduplication?
**✅ Per-Scan** - Use `(scan_job_id, url_hash)` unique constraint. Allows tracking URL changes over time.

### ❓ How to store headers?
**✅ JSONB** - Flexible and queryable. Can find endpoints by server, content-type, or any custom header.

### ❓ What about technologies and forms?
**⏳ Deferred** - Not present in current test output. Add tables when feature is enabled.

---

## Documentation

📄 **Full Analysis:** `katana_output_analysis.md` (detailed schema, query patterns, code examples)  
📋 **Test Container Plan:** `katana_test_container_20251120.md`  
📦 **Test Output:** `backend/containers/katana-test/output/results.json`

---

**Status:** Ready for schema implementation  
**Confidence Level:** High - Real test data analyzed  
**Risk Level:** Low - Conservative design with proven patterns

