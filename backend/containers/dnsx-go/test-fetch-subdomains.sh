#!/bin/bash
# =====================================================================
# DNSX Database Fetch Test Script
# =====================================================================
# Purpose: Test DNSX container with FETCH_SUBDOMAINS mode
# Phase: 5A - Database Fetch Mechanism
# Date: October 28, 2025
# =====================================================================

set -e

echo "🧪 DNSX Database Fetch Test"
echo "====================================================================="

# Check if required env vars are set
if [ -z "$SUPABASE_URL" ]; then
    echo "❌ Error: SUPABASE_URL environment variable not set"
    echo "   Export it first: export SUPABASE_URL='https://your-project.supabase.co'"
    exit 1
fi

if [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "❌ Error: SUPABASE_SERVICE_ROLE_KEY environment variable not set"
    echo "   Export it first: export SUPABASE_SERVICE_ROLE_KEY='your-service-key'"
    exit 1
fi

if [ -z "$TEST_ASSET_ID" ]; then
    echo "❌ Error: TEST_ASSET_ID environment variable not set"
    echo "   Export it first: export TEST_ASSET_ID='your-asset-uuid'"
    echo "   (Use an asset that has subdomains in the database)"
    exit 1
fi

# Generate test IDs
TEST_BATCH_ID=$(uuidgen)

echo "Configuration:"
echo "  Supabase URL:    ${SUPABASE_URL}"
echo "  Asset ID:        ${TEST_ASSET_ID}"
echo "  Batch ID:        ${TEST_BATCH_ID}"
echo "  Mode:            FETCH_SUBDOMAINS"
echo "====================================================================="
echo ""

echo "📦 Running DNSX container with database fetch..."
echo ""

# Run container with FETCH_SUBDOMAINS
docker run --rm \
  -e BATCH_MODE=true \
  -e BATCH_ID="${TEST_BATCH_ID}" \
  -e MODULE_TYPE=dnsx \
  -e FETCH_SUBDOMAINS=true \
  -e ASSET_ID="${TEST_ASSET_ID}" \
  -e SUPABASE_URL="${SUPABASE_URL}" \
  -e SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY}" \
  dnsx-scanner:phase5a-test

echo ""
echo "====================================================================="
echo "✅ Test completed!"
echo ""
echo "🔍 Verification steps:"
echo "   1. Check if container fetched subdomains from database"
echo "   2. Verify DNS records were resolved"
echo "   3. Confirm records inserted to dns_records table"
echo ""
echo "📊 Query DNS records:"
echo "   SELECT COUNT(*) FROM dns_records WHERE batch_scan_id = '${TEST_BATCH_ID}';"
echo ""
echo "   SELECT subdomain, record_type, record_value"
echo "   FROM dns_records"
echo "   WHERE batch_scan_id = '${TEST_BATCH_ID}'"
echo "   LIMIT 10;"
echo "====================================================================="
