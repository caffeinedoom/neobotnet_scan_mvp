#!/bin/zsh
# Reconnaissance Testing Script
# Usage: ./test-recon.sh [payload-file]

API_BASE="https://aldous-api.neobotnet.com"
DATA_DIR="../data"
PAYLOAD_FILE=${1:-"scan-debug.json"}

echo "🔍 Testing Reconnaissance Flow"
echo "=============================="

# Check if token exists
if [[ ! -f /tmp/jwt_token.txt ]]; then
    echo "❌ No JWT token found. Run test-auth.sh first"
    exit 1
fi

TOKEN=$(cat /tmp/jwt_token.txt)
echo "🔑 Using saved JWT token"

echo ""
echo "📍 Step 1: Recon Service Health"
curl -s ${API_BASE}/api/v1/recon/health | jq .

echo ""
echo "📍 Step 2: Starting Subdomain Scan"
echo "   Payload: ${PAYLOAD_FILE}"

curl -s -X POST ${API_BASE}/api/v1/recon/subdomain/scan \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d @${DATA_DIR}/${PAYLOAD_FILE} | jq . > /tmp/scan_response.json

echo "✅ Scan response saved to /tmp/scan_response.json"
cat /tmp/scan_response.json
