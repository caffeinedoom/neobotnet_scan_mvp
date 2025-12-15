#!/bin/bash
# Test script for Subfinder streaming mode
# Usage: ./test_streaming.sh

set -e  # Exit on error

echo "🧪 Testing Subfinder Streaming Mode"
echo "===================================="

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Start it with: docker run -d -p 6379:6379 redis:7-alpine"
    exit 1
fi

echo "✅ Redis is running"

# Generate unique test IDs
TEST_SCAN_JOB_ID="test-scan-$(date +%s)"
TEST_STREAM_KEY="scan:${TEST_SCAN_JOB_ID}:subfinder:output"

echo "📋 Test configuration:"
echo "   SCAN_JOB_ID: $TEST_SCAN_JOB_ID"
echo "   STREAM_KEY: $TEST_STREAM_KEY"

# Clean up any existing test stream
redis-cli DEL "$TEST_STREAM_KEY" > /dev/null 2>&1 || true

# Set environment variables
export STREAMING_MODE=true
export STREAM_OUTPUT_KEY="$TEST_STREAM_KEY"
export REDIS_HOST=localhost
export REDIS_PORT=6379
export SCAN_JOB_ID="$TEST_SCAN_JOB_ID"
export USER_ID="test-user-123"
export SUPABASE_URL="${SUPABASE_URL:-https://placeholder.supabase.co}"
export SUPABASE_SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-placeholder-key}"
export BATCH_MODE=false
export DOMAINS='["example.com"]'

echo ""
echo "🚀 Running Subfinder in streaming mode..."
echo ""

# Run subfinder (compile if needed)
if [ ! -f "./subfinder-go" ]; then
    echo "📦 Compiling Subfinder..."
    go build -o subfinder-go .
fi

# Run subfinder with timeout
timeout 60s ./subfinder-go || true

echo ""
echo "🔍 Checking Redis Stream..."
echo ""

# Check stream length
STREAM_LENGTH=$(redis-cli XLEN "$TEST_STREAM_KEY")
echo "✅ Stream length: $STREAM_LENGTH messages"

if [ "$STREAM_LENGTH" -gt 0 ]; then
    echo ""
    echo "📤 First 5 messages in stream:"
    redis-cli XRANGE "$TEST_STREAM_KEY" - + COUNT 5
    
    echo ""
    echo "🏁 Last message (should be completion marker):"
    redis-cli XREVRANGE "$TEST_STREAM_KEY" + - COUNT 1
    
    echo ""
    echo "✅ TEST PASSED: Streaming mode is working!"
else
    echo "❌ TEST FAILED: No messages in stream"
    exit 1
fi

# Cleanup
echo ""
echo "🧹 Cleaning up..."
redis-cli DEL "$TEST_STREAM_KEY" > /dev/null

echo "✅ Test complete"
