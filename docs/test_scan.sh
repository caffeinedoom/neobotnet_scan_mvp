#!/bin/bash

################################################################################
# Scan Engine Testing Script
# 
# Purpose: Automated end-to-end testing of the unified scan endpoint
# Based on: test_results_2025_11_11.md
# 
# Usage:
#   ./test_scan.sh --asset-id <UUID>
#   ./test_scan.sh -a <UUID>
#
# Example:
#   ./test_scan.sh --asset-id 6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e
#
# Features:
#   - Cookie-based authentication
#   - Scan triggering via unified endpoint
#   - Automatic progress monitoring (polling)
#   - CloudWatch log retrieval with correlation IDs
#   - Comprehensive test results summary
#
# Requirements:
#   - curl (for API requests)
#   - jq (for JSON parsing)
#   - AWS CLI (for CloudWatch logs)
#
################################################################################

# Color codes for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default configuration
API_BASE_URL="https://aldous-api.neobotnet.com"
COOKIES_FILE="/tmp/scan_test_cookies_$$.txt"  # $$ = current process ID (unique per run)
AWS_REGION="us-east-1"
LOG_GROUP="/aws/ecs/neobotnet-v2-dev"

# Test configuration
POLL_INTERVAL=10  # Seconds between status polls
MAX_POLLS=18      # Maximum number of polls (18 * 10s = 3 minutes)

# Login credentials (set via environment variables for security)
EMAIL="${SCAN_TEST_EMAIL:-sam@pluck.ltd}"
PASSWORD="${SCAN_TEST_PASSWORD}"

# Scan modules to use (can be overridden with --modules flag)
MODULES='["subfinder", "dnsx"]'
ACTIVE_DOMAINS_ONLY=true

################################################################################
# Functions
################################################################################

# Print colored messages
print_header() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Display usage information
usage() {
    cat << EOF
${GREEN}Scan Engine Testing Script${NC}

${BLUE}Usage:${NC}
  $0 --asset-id <UUID> [--modules <JSON>]
  $0 -a <UUID> [-m <JSON>]

${BLUE}Options:${NC}
  -a, --asset-id <UUID>    Asset ID to scan (required)
  -m, --modules <JSON>     Modules to run (default: ["subfinder", "dnsx"])
  -h, --help               Show this help message

${BLUE}Environment Variables:${NC}
  SCAN_TEST_EMAIL          Email for login (default: sam@pluck.ltd)
  SCAN_TEST_PASSWORD       Password for login (required)

${BLUE}Examples:${NC}
  # Test subfinder + dnsx (default)
  export SCAN_TEST_PASSWORD="your-password"
  $0 --asset-id 6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e

  # Test subfinder + httpx
  $0 -a 6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e -m '["subfinder", "httpx"]'

  # Test all three modules
  $0 -a 6f58e77d-b8ee-44a3-9e5e-7787db5e4e2e -m '["subfinder", "dnsx", "httpx"]'

${BLUE}Requirements:${NC}
  - curl (for API requests)
  - jq (for JSON parsing)
  - AWS CLI (for CloudWatch logs)

EOF
    exit 1
}

# Check required dependencies
check_dependencies() {
    local missing_deps=()
    
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi
    
    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    fi
    
    if ! command -v aws &> /dev/null; then
        missing_deps+=("aws")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        echo ""
        echo "Install them with:"
        echo "  Ubuntu/Debian: sudo apt-get install curl jq awscli"
        echo "  MacOS: brew install curl jq awscli"
        exit 1
    fi
}

# Cleanup temporary files on exit
cleanup() {
    if [ -f "$COOKIES_FILE" ]; then
        rm -f "$COOKIES_FILE"
        print_info "Cleaned up temporary files"
    fi
}

# Register cleanup function to run on exit
trap cleanup EXIT

################################################################################
# Step 1: Login and Get Authentication Cookie
################################################################################
login() {
    print_header "Step 1: Authentication"
    
    if [ -z "$PASSWORD" ]; then
        print_error "Password not set. Please set SCAN_TEST_PASSWORD environment variable."
        echo ""
        echo "Example:"
        echo "  export SCAN_TEST_PASSWORD='your-password'"
        exit 1
    fi
    
    print_info "Logging in as: $EMAIL"
    
    # Make login request and save cookies to file
    local response=$(curl -s -X POST "$API_BASE_URL/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" \
        -c "$COOKIES_FILE")
    
    # Check if login was successful
    local message=$(echo "$response" | jq -r '.message // empty')
    
    if [ "$message" = "Login successful" ]; then
        local user_id=$(echo "$response" | jq -r '.user.id')
        print_success "Login successful"
        print_info "User ID: $user_id"
        
        # Verify cookie file was created
        if [ ! -f "$COOKIES_FILE" ]; then
            print_error "Cookie file not created"
            exit 1
        fi
        
        return 0
    else
        print_error "Login failed"
        echo "$response" | jq .
        exit 1
    fi
}

################################################################################
# Step 2: Trigger Scan
################################################################################
trigger_scan() {
    print_header "Step 2: Trigger Scan"
    
    print_info "Asset ID: $ASSET_ID"
    print_info "Modules: $(echo $MODULES | jq -r '. | join(", ")')"
    print_info "Active domains only: $ACTIVE_DOMAINS_ONLY"
    
    # Record start time for response time calculation
    local start_time=$(date +%s)
    
    # Prepare request body
    local request_body=$(cat <<EOF
{
  "assets": {
    "$ASSET_ID": {
      "modules": $MODULES,
      "active_domains_only": $ACTIVE_DOMAINS_ONLY
    }
  }
}
EOF
)
    
    # Make scan request
    local response=$(curl -s -X POST "$API_BASE_URL/api/v1/scans" \
        -b "$COOKIES_FILE" \
        -H "Content-Type: application/json" \
        -d "$request_body")
    
    # Calculate response time
    local end_time=$(date +%s)
    local response_time=$((end_time - start_time))
    
    # Parse response
    SCAN_ID=$(echo "$response" | jq -r '.scan_id // empty')
    
    if [ -z "$SCAN_ID" ]; then
        print_error "Failed to trigger scan"
        echo "Response:"
        echo "$response" | jq .
        exit 1
    fi
    
    # Extract scan details
    local status=$(echo "$response" | jq -r '.status')
    local assets_count=$(echo "$response" | jq -r '.assets_count')
    local total_domains=$(echo "$response" | jq -r '.total_domains')
    local execution_mode=$(echo "$response" | jq -r '.execution_mode // "unknown"')
    
    print_success "Scan triggered successfully"
    echo ""
    echo "  Scan ID:          $SCAN_ID"
    echo "  Status:           $status"
    echo "  Assets Count:     $assets_count"
    echo "  Total Domains:    $total_domains"
    echo "  Execution Mode:   $execution_mode"
    echo "  Response Time:    ${response_time}s"
    echo ""
    
    # Save scan ID short form for CloudWatch logs
    SCAN_ID_SHORT="${SCAN_ID:0:8}"
    
    # Check response time
    if [ $response_time -le 2 ]; then
        print_success "Response time: ${response_time}s (✅ Fast, non-blocking)"
    else
        print_warning "Response time: ${response_time}s (⚠️  Slower than expected)"
    fi
}

################################################################################
# Step 3: Monitor Scan Progress
################################################################################
monitor_scan() {
    print_header "Step 3: Monitor Scan Progress"
    
    print_info "Polling interval: ${POLL_INTERVAL}s"
    print_info "Maximum polls: $MAX_POLLS (${MAX_POLLS}0 seconds total)"
    print_info "Correlation ID: [$SCAN_ID_SHORT]"
    echo ""
    
    local poll_count=0
    local scan_start_time=$(date +%s)
    
    while [ $poll_count -lt $MAX_POLLS ]; do
        poll_count=$((poll_count + 1))
        
        # Get current time for display
        local current_time=$(date +%H:%M:%S)
        
        # Poll scan status
        local response=$(curl -s -X GET "$API_BASE_URL/api/v1/scans/$SCAN_ID" \
            -b "$COOKIES_FILE")
        
        # Extract status and progress
        local status=$(echo "$response" | jq -r '.status')
        local completed_assets=$(echo "$response" | jq -r '.completed_assets // 0')
        local failed_assets=$(echo "$response" | jq -r '.failed_assets // 0')
        local assets_count=$(echo "$response" | jq -r '.assets_count // 1')
        
        # Display poll result
        echo -e "${BLUE}📊 Poll $poll_count/$MAX_POLLS${NC} ($current_time):"
        echo "   Status: $status"
        echo "   Progress: $completed_assets/$assets_count assets completed"
        echo "   Failed: $failed_assets"
        
        # Check if scan is complete
        if [ "$status" = "completed" ] || [ "$status" = "failed" ] || [ "$status" = "cancelled" ]; then
            echo ""
            
            # Calculate total duration
            local scan_end_time=$(date +%s)
            local total_duration=$((scan_end_time - scan_start_time))
            
            if [ "$status" = "completed" ]; then
                print_success "Scan finished: $status"
            else
                print_error "Scan finished: $status"
            fi
            
            echo ""
            echo "  Total Duration: ${total_duration}s (~$((total_duration / 60))m $((total_duration % 60))s)"
            echo ""
            
            # Display final results
            print_info "Final Results:"
            echo "$response" | jq '{
                id,
                status,
                assets_count,
                completed_assets,
                failed_assets,
                total_domains,
                completed_domains,
                created_at,
                started_at,
                completed_at,
                results,
                metadata
            }'
            
            # Store final status for summary
            FINAL_STATUS="$status"
            FINAL_DURATION="$total_duration"
            FINAL_RESPONSE="$response"
            
            return 0
        fi
        
        # Wait before next poll (skip on last poll)
        if [ $poll_count -lt $MAX_POLLS ]; then
            sleep $POLL_INTERVAL
        fi
    done
    
    # If we reach here, scan didn't complete in time
    print_warning "Maximum polls reached. Scan may still be running."
    FINAL_STATUS="timeout"
    FINAL_DURATION=$((MAX_POLLS * POLL_INTERVAL))
    
    return 1
}

################################################################################
# Step 4: Check CloudWatch Logs
################################################################################
check_logs() {
    print_header "Step 4: CloudWatch Logs"
    
    print_info "Searching for correlation ID: [$SCAN_ID_SHORT]"
    print_info "Log Group: $LOG_GROUP"
    print_info "Time Range: Last 15 minutes"
    echo ""
    
    # Calculate start time (15 minutes ago in milliseconds)
    local start_time=$(date -d '15 minutes ago' +%s)000
    
    # Fetch logs from CloudWatch
    print_info "Fetching logs... (this may take a few seconds)"
    
    local logs=$(aws logs filter-log-events \
        --log-group-name "$LOG_GROUP" \
        --start-time "$start_time" \
        --filter-pattern "$SCAN_ID_SHORT" \
        --query 'events[*].message' \
        --output text \
        --region "$AWS_REGION" 2>&1)
    
    # Check if AWS CLI succeeded
    if [ $? -ne 0 ]; then
        print_warning "Failed to fetch CloudWatch logs"
        echo "Error: $logs"
        echo ""
        print_info "You may need to configure AWS credentials:"
        echo "  aws configure"
        return 1
    fi
    
    # Check if logs were found
    if [ -z "$logs" ]; then
        print_warning "No logs found for correlation ID: [$SCAN_ID_SHORT]"
        return 1
    fi
    
    print_success "Logs retrieved"
    echo ""
    
    # Display key log entries
    echo "═══════════════════════════════════════════════════════════════════════════"
    echo "Key Log Entries (filtered for [$SCAN_ID_SHORT]):"
    echo "═══════════════════════════════════════════════════════════════════════════"
    echo ""
    
    # Filter and display important log lines
    echo "$logs" | grep -E "\[${SCAN_ID_SHORT}\]" | head -50
    
    echo ""
    echo "═══════════════════════════════════════════════════════════════════════════"
    
    # Check for errors
    local error_count=$(echo "$logs" | grep -ci "ERROR\|Exception\|Traceback")
    
    if [ $error_count -eq 0 ]; then
        print_success "No errors found in logs"
    else
        print_warning "Found $error_count potential error(s) in logs"
        echo ""
        echo "Error excerpts:"
        echo "$logs" | grep -i "ERROR\|Exception\|Traceback" | head -10
    fi
}

################################################################################
# Step 5: Display Test Summary
################################################################################
display_summary() {
    print_header "Test Summary"
    
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║                           SCAN TEST RESULTS                               ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    echo "Test Configuration:"
    echo "  Asset ID:         $ASSET_ID"
    echo "  Scan ID:          $SCAN_ID"
    echo "  Correlation ID:   [$SCAN_ID_SHORT]"
    echo "  Modules:          $(echo $MODULES | jq -r '. | join(", ")')"
    echo ""
    
    echo "Results:"
    echo "  Final Status:     $FINAL_STATUS"
    echo "  Total Duration:   ${FINAL_DURATION}s (~$((FINAL_DURATION / 60))m $((FINAL_DURATION % 60))s)"
    
    if [ -n "$FINAL_RESPONSE" ]; then
        local completed_assets=$(echo "$FINAL_RESPONSE" | jq -r '.completed_assets // 0')
        local failed_assets=$(echo "$FINAL_RESPONSE" | jq -r '.failed_assets // 0')
        local assets_count=$(echo "$FINAL_RESPONSE" | jq -r '.assets_count // 1')
        local total_subdomains=$(echo "$FINAL_RESPONSE" | jq -r '.results.total_subdomains // 0')
        
        echo "  Completed Assets: $completed_assets/$assets_count"
        echo "  Failed Assets:    $failed_assets"
        echo "  Subdomains Found: $total_subdomains"
    fi
    
    echo ""
    
    # Overall test status
    if [ "$FINAL_STATUS" = "completed" ]; then
        print_success "TEST PASSED ✅"
        echo ""
        echo "The unified scan endpoint is working correctly!"
        return 0
    elif [ "$FINAL_STATUS" = "failed" ]; then
        print_error "TEST FAILED ❌"
        echo ""
        echo "The scan completed but with failures. Check the logs above."
        return 1
    elif [ "$FINAL_STATUS" = "timeout" ]; then
        print_warning "TEST TIMEOUT ⏱️"
        echo ""
        echo "The scan did not complete within the timeout period."
        echo "Check CloudWatch logs for more details."
        return 1
    else
        print_warning "TEST INCOMPLETE ⚠️"
        echo ""
        echo "The scan ended with unexpected status: $FINAL_STATUS"
        return 1
    fi
}

################################################################################
# Main Script
################################################################################

main() {
    # Display script header
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════════════╗"
    echo "║              Unified Scan Endpoint - Automated Testing Script            ║"
    echo "║                      Based on: test_results_2025_11_11.md                ║"
    echo "╚═══════════════════════════════════════════════════════════════════════════╝"
    
    # Parse command line arguments
    ASSET_ID=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -a|--asset-id)
                ASSET_ID="$2"
                shift 2
                ;;
            -m|--modules)
                MODULES="$2"
                shift 2
                ;;
            -h|--help)
                usage
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                ;;
        esac
    done
    
    # Validate asset ID was provided
    if [ -z "$ASSET_ID" ]; then
        print_error "Asset ID is required"
        echo ""
        usage
    fi
    
    # Check dependencies
    check_dependencies
    
    # Execute test steps
    login
    trigger_scan
    monitor_scan
    check_logs
    
    echo ""
    
    # Display summary and exit with appropriate code
    display_summary
    exit $?
}

# Run main function
main "$@"
