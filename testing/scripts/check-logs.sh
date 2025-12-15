#!/bin/zsh
# CloudWatch Logs Checking Script
# Usage: ./check-logs.sh [minutes-back]

MINUTES_BACK=${1:-5}
LOG_GROUP="/aws/ecs/neobotnet-v2-dev"

echo "📊 Checking CloudWatch Logs"
echo "============================"
echo "⏰ Looking back ${MINUTES_BACK} minutes"

# Get latest log stream
LATEST_STREAM=$(aws logs describe-log-streams \
  --log-group-name ${LOG_GROUP} \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --query 'logStreams[0].logStreamName' \
  --output text)

echo "📄 Latest log stream: ${LATEST_STREAM}"

# Calculate timestamp
START_TIME=$(($(date +%s)*1000 - ${MINUTES_BACK}*60*1000))

echo ""
echo "🔍 Recent log entries:"
aws logs get-log-events \
  --log-group-name ${LOG_GROUP} \
  --log-stream-name ${LATEST_STREAM} \
  --start-time ${START_TIME} \
  --query 'events[*].message' \
  --output text | grep -E "(DEBUG|ERROR|recon|POST|scan)" | tail -20
