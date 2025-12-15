#!/bin/zsh
# Master Testing Script
# Usage: ./run-all-tests.sh

echo "🚀 Web Reconnaissance Framework - Full Test Suite"
echo "=================================================="

# Change to scripts directory
cd "$(dirname "$0")"

echo ""
echo "📍 Test 1: Authentication Flow"
./test-auth.sh

echo ""
echo "📍 Test 2: Reconnaissance with Debug Payload"
./test-recon.sh scan-debug.json

echo ""
echo "📍 Test 3: Check Recent Logs"
./check-logs.sh 2

echo ""
echo "✅ All tests completed!"
echo "📁 Results saved in /tmp/"
echo "   - /tmp/login_response.json"
echo "   - /tmp/scan_response.json"
echo "   - /tmp/jwt_token.txt"
