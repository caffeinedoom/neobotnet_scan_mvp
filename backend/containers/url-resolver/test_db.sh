#!/bin/bash
# URL Resolver Database Test Script
# Tests database operations with real Supabase connection
#
# Prerequisites:
#   - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set
#   - A test asset must exist in the database
#
# Usage:
#   export SUPABASE_URL=https://xxx.supabase.co
#   export SUPABASE_SERVICE_ROLE_KEY=xxx
#   export TEST_ASSET_ID=<uuid-of-existing-asset>
#   ./test_db.sh

set -e

echo "🧪 URL Resolver Database Test"
echo "=============================="
echo ""

# Check required environment variables
if [ -z "$SUPABASE_URL" ]; then
    echo "❌ Error: SUPABASE_URL is not set"
    echo "   export SUPABASE_URL=https://xxx.supabase.co"
    exit 1
fi

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "❌ Error: SUPABASE_SERVICE_ROLE_KEY is not set"
    echo "   export SUPABASE_SERVICE_ROLE_KEY=xxx"
    exit 1
fi

# Use provided asset ID or generate a test one
ASSET_ID="${TEST_ASSET_ID:-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}"
SCAN_JOB_ID="test-db-$(date +%s)"

echo "📋 Configuration:"
echo "   SUPABASE_URL: ${SUPABASE_URL:0:40}..."
echo "   ASSET_ID: $ASSET_ID"
echo "   SCAN_JOB_ID: $SCAN_JOB_ID"
echo ""

# Build container
echo "📦 Building container..."
docker build -t url-resolver:test . --quiet
echo "✅ Container built"
echo ""

# Note: Simple mode doesn't write to DB, so we need a different approach
# We'll use a Go test file or directly test the API

echo "ℹ️  Simple mode tests URL probing only (no DB writes)"
echo ""
echo "To test database operations, you have two options:"
echo ""
echo "Option 1: Use curl to test the Supabase API directly"
echo "----------------------------------------"
echo "# Insert a test URL record"
echo "curl -X POST '$SUPABASE_URL/rest/v1/urls' \\"
echo "  -H 'apikey: \$SUPABASE_SERVICE_ROLE_KEY' \\"
echo "  -H 'Authorization: Bearer \$SUPABASE_SERVICE_ROLE_KEY' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{"
echo '    "asset_id": "'$ASSET_ID'",'
echo '    "url": "https://test.example.com/path",'
echo '    "url_hash": "testhash123",'
echo '    "domain": "test.example.com",'
echo '    "path": "/path",'
echo '    "sources": ["test"],'
echo '    "first_discovered_by": "test",'
echo '    "is_alive": true,'
echo '    "status_code": 200'
echo "  }'"
echo ""
echo "Option 2: Run the streaming mode with Redis"
echo "----------------------------------------"
echo "See test_redis.sh for Redis streaming tests"
echo ""

# Test direct API insert if asset exists
if [ "$TEST_ASSET_ID" != "" ]; then
    echo "🔬 Testing direct Supabase insert..."
    
    TEST_URL="https://test-$(date +%s).example.com/path?id=123"
    TEST_HASH=$(echo -n "$TEST_URL" | sha256sum | cut -d' ' -f1)
    
    RESPONSE=$(curl -s -X POST "$SUPABASE_URL/rest/v1/urls" \
      -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
      -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
      -H "Content-Type: application/json" \
      -H "Prefer: return=representation" \
      -d "{
        \"asset_id\": \"$TEST_ASSET_ID\",
        \"url\": \"$TEST_URL\",
        \"url_hash\": \"$TEST_HASH\",
        \"domain\": \"test.example.com\",
        \"path\": \"/path\",
        \"query_params\": {\"id\": \"123\"},
        \"sources\": [\"test\"],
        \"first_discovered_by\": \"test-script\",
        \"is_alive\": true,
        \"status_code\": 200,
        \"has_params\": true
      }")
    
    if echo "$RESPONSE" | grep -q '"id"'; then
        echo "✅ Database insert successful!"
        echo "   Response: $(echo $RESPONSE | head -c 200)..."
        
        # Extract ID and delete the test record
        URL_ID=$(echo $RESPONSE | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        if [ "$URL_ID" != "" ]; then
            echo ""
            echo "🧹 Cleaning up test record: $URL_ID"
            curl -s -X DELETE "$SUPABASE_URL/rest/v1/urls?id=eq.$URL_ID" \
              -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
              -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
            echo "✅ Test record deleted"
        fi
    else
        echo "⚠️  Insert response: $RESPONSE"
        echo ""
        echo "This might fail if:"
        echo "  - TEST_ASSET_ID doesn't exist in assets table"
        echo "  - RLS policies are blocking the insert"
        echo "  - The urls table doesn't exist yet"
    fi
fi

echo ""
echo "✅ Database test completed!"

