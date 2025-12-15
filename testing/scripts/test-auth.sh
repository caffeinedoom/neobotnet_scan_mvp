#!/bin/zsh
# Authentication Testing Script
# Usage: ./test-auth.sh

API_BASE="https://aldous-api.neobotnet.com"
DATA_DIR="../data"

echo "🔐 Testing Authentication Flow"
echo "============================="

echo "📍 Step 1: API Health Check"
curl -s ${API_BASE}/health | jq .

echo ""
echo "📍 Step 2: User Login"
curl -s -X POST ${API_BASE}/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d @${DATA_DIR}/login.json | jq . > /tmp/login_response.json

echo "✅ Login response saved to /tmp/login_response.json"

# Extract token for further use
TOKEN=$(jq -r '.access_token' /tmp/login_response.json)
echo "🔑 JWT Token extracted (length: ${#TOKEN})"

# Save token for other tests
echo ${TOKEN} > /tmp/jwt_token.txt
echo "💾 Token saved to /tmp/jwt_token.txt"
