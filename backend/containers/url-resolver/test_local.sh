#!/bin/bash
# URL Resolver Local Test Script
# Tests core functionality without Redis/Supabase dependencies

set -e

echo "🧪 URL Resolver Local Testing"
echo "=============================="
echo ""

# Build if not already built
echo "📦 Building container..."
docker build -t url-resolver:test . --quiet

echo ""
echo "✅ Container built successfully"
echo ""

# Test 1: Basic URL
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TEST 1: Basic HTTPS URL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker run --rm \
  -e STREAMING_MODE=false \
  -e TEST_URL="https://example.com" \
  -e SCAN_JOB_ID="test-1" \
  -e SUPABASE_URL="https://test.supabase.co" \
  -e SUPABASE_SERVICE_ROLE_KEY="test-key" \
  url-resolver:test

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TEST 2: URL with Path and Query Parameters"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker run --rm \
  -e STREAMING_MODE=false \
  -e TEST_URL="https://httpbin.org/get?foo=bar&test=123" \
  -e SCAN_JOB_ID="test-2" \
  -e SUPABASE_URL="https://test.supabase.co" \
  -e SUPABASE_SERVICE_ROLE_KEY="test-key" \
  url-resolver:test

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TEST 3: URL with File Extension"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker run --rm \
  -e STREAMING_MODE=false \
  -e TEST_URL="https://raw.githubusercontent.com/golang/go/master/README.md" \
  -e SCAN_JOB_ID="test-3" \
  -e SUPABASE_URL="https://test.supabase.co" \
  -e SUPABASE_SERVICE_ROLE_KEY="test-key" \
  url-resolver:test

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TEST 4: Non-Existent Domain (Should Show Dead)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker run --rm \
  -e STREAMING_MODE=false \
  -e TEST_URL="https://this-domain-definitely-does-not-exist-12345.com" \
  -e SCAN_JOB_ID="test-4" \
  -e SUPABASE_URL="https://test.supabase.co" \
  -e SUPABASE_SERVICE_ROLE_KEY="test-key" \
  url-resolver:test

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "TEST 5: URL with Redirect (httpbin redirects)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker run --rm \
  -e STREAMING_MODE=false \
  -e TEST_URL="https://httpbin.org/redirect/2" \
  -e SCAN_JOB_ID="test-5" \
  -e SUPABASE_URL="https://test.supabase.co" \
  -e SUPABASE_SERVICE_ROLE_KEY="test-key" \
  url-resolver:test

echo ""
echo "✅ All local tests completed!"
echo ""
echo "Next steps:"
echo "  1. Test with real Redis: docker-compose up redis && ./test_redis.sh"
echo "  2. Test with real Supabase: export SUPABASE_URL=... && ./test_db.sh"
echo "  3. Run full pipeline test"

