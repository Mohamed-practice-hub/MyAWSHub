#!/bin/bash
# Automated Lambda Deployment Script for Swing Trading System
# Detects changes and redeploys Lambda functions automatically

set -e  # Exit on any error

# Configuration
LAMBDA_DIR="../Lambda"
MAIN_FUNCTION="swing-automation-data-processor-lambda"
PERFORMANCE_FUNCTION="swing-performance-analyzer"
SENTIMENT_FUNCTION="swing-sentiment-enhanced-lambda"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Swing Trading Lambda Auto-Deployment Script${NC}"
echo "=================================================="

# Function to check if Lambda function exists
check_function_exists() {
    local function_name=$1
    if aws lambda get-function --function-name "$function_name" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to get current function hash
get_function_hash() {
    local function_name=$1
    aws lambda get-function --function-name "$function_name" --query 'Configuration.CodeSha256' --output text 2>/dev/null || echo "none"
}

# Function to calculate local file hash
get_local_hash() {
    local file_path=$1
    if [[ -f "$file_path" ]]; then
        sha256sum "$file_path" | cut -d' ' -f1
    else
        echo "none"
    fi
}

# Function to deploy main trading bot
deploy_main_function() {
    echo -e "${YELLOW}📦 Deploying Main Trading Bot Lambda...${NC}"
    
    pushd "$LAMBDA_DIR" >/dev/null
    
    # Create deployment package
    echo "Creating deployment package..."
    powershell -Command "Compress-Archive -Path lambda_function.py,requests*,urllib3*,certifi*,charset_normalizer*,idna* -DestinationPath lambda_function.zip -Force" >/dev/null
    
    # Update function code
    aws lambda update-function-code \
        --function-name "$MAIN_FUNCTION" \
        --zip-file fileb://lambda_function.zip >/dev/null
    
    echo -e "${GREEN}✅ Main function deployed successfully${NC}"
    
    # Cleanup
    rm -f lambda_function.zip
    popd >/dev/null
}

# Function to deploy performance analyzer
deploy_performance_function() {
    echo -e "${YELLOW}📊 Deploying Performance Analyzer Lambda...${NC}"
    
    pushd "$LAMBDA_DIR" >/dev/null
    
    # Create deployment package
    echo "Creating deployment package..."
    powershell -Command "Compress-Archive -Path performance-analyzer.py,requests*,urllib3*,certifi*,charset_normalizer*,idna* -DestinationPath swing-performance.zip -Force" >/dev/null
    
    # Update function code
    aws lambda update-function-code \
        --function-name "$PERFORMANCE_FUNCTION" \
        --zip-file fileb://swing-performance.zip >/dev/null
    
    echo -e "${GREEN}✅ Performance analyzer deployed successfully${NC}"
    
    # Cleanup
    rm -f swing-performance.zip
    popd >/dev/null
}

# Function to deploy sentiment-enhanced function
deploy_sentiment_function() {
    echo -e "${YELLOW}🧠 Deploying Sentiment-Enhanced Lambda...${NC}"
    
    pushd "$LAMBDA_DIR" >/dev/null
    
    # Check if pandas/numpy are installed
    if [[ ! -d "pandas" ]]; then
        echo "Installing additional dependencies..."
        pip install --no-user pandas numpy -t . >/dev/null 2>&1
    fi
    
    # Create deployment package
    echo "Creating deployment package..."
    powershell -Command "Compress-Archive -Path sentiment-enhanced-lambda.py,requests*,pandas*,numpy*,urllib3*,certifi*,charset_normalizer*,idna*,boto3*,dateutil*,pytz*,six* -DestinationPath sentiment-enhanced-lambda.zip -Force" >/dev/null
    
    # Update function code
    aws lambda update-function-code \
        --function-name "$SENTIMENT_FUNCTION" \
        --zip-file fileb://sentiment-enhanced-lambda.zip >/dev/null
    
    echo -e "${GREEN}✅ Sentiment-enhanced function deployed successfully${NC}"
    
    # Cleanup
    rm -f sentiment-enhanced-lambda.zip
    popd >/dev/null
}

# Function to test Lambda function
test_function() {
    local function_name=$1
    local test_payload=$2
    
    echo "Testing $function_name..."
    
    # Create temporary test file in current directory
    echo "$test_payload" > test-payload.json
    
    # Invoke function
    local result=$(aws lambda invoke \
        --function-name "$function_name" \
        --payload fileb://test-payload.json \
        --query 'StatusCode' \
        --output text \
        lambda-response.json 2>/dev/null)
    
    if [[ "$result" == "200" ]]; then
        echo -e "${GREEN}✅ Test passed${NC}"
    else
        echo -e "${RED}❌ Test failed (Status: $result)${NC}"
        if [[ -f "lambda-response.json" ]]; then
            echo "Response:"
            cat lambda-response.json
        fi
    fi
    
    # Cleanup
    rm -f test-payload.json lambda-response.json
}

# Main deployment logic
main() {
    echo "Checking for changes and deploying Lambda functions..."
    echo ""
    
    # Check main trading bot
    if check_function_exists "$MAIN_FUNCTION"; then
        local current_hash=$(get_function_hash "$MAIN_FUNCTION")
        local local_hash=$(get_local_hash "$LAMBDA_DIR/lambda_function.py")
        
        echo -e "${BLUE}Main Trading Bot:${NC}"
        echo "  Current: ${current_hash:0:12}..."
        echo "  Local:   ${local_hash:0:12}..."
        
        if [[ "$current_hash" != "$local_hash" ]] || [[ "$1" == "--force" ]]; then
            deploy_main_function
            echo -e "${BLUE}ℹ️ Skipping test (deployment successful)${NC}"
        else
            echo -e "${GREEN}✅ No changes detected${NC}"
        fi
    else
        echo -e "${RED}❌ Main function not found. Deploy manually first.${NC}"
    fi
    
    echo ""
    
    # Check performance analyzer
    if check_function_exists "$PERFORMANCE_FUNCTION"; then
        local current_hash=$(get_function_hash "$PERFORMANCE_FUNCTION")
        local local_hash=$(get_local_hash "$LAMBDA_DIR/performance-analyzer.py")
        
        echo -e "${BLUE}Performance Analyzer:${NC}"
        echo "  Current: ${current_hash:0:12}..."
        echo "  Local:   ${local_hash:0:12}..."
        
        if [[ "$current_hash" != "$local_hash" ]] || [[ "$1" == "--force" ]]; then
            deploy_performance_function
            echo -e "${BLUE}ℹ️ Skipping test (deployment successful)${NC}"
        else
            echo -e "${GREEN}✅ No changes detected${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️ Performance analyzer not found. Skipping.${NC}"
    fi
    
    echo ""
    
    # Check sentiment-enhanced function (optional)
    if check_function_exists "$SENTIMENT_FUNCTION"; then
        local current_hash=$(get_function_hash "$SENTIMENT_FUNCTION")
        local local_hash=$(get_local_hash "$LAMBDA_DIR/sentiment-enhanced-lambda.py")
        
        echo -e "${BLUE}Sentiment-Enhanced:${NC}"
        echo "  Current: ${current_hash:0:12}..."
        echo "  Local:   ${local_hash:0:12}..."
        
        if [[ "$current_hash" != "$local_hash" ]] || [[ "$1" == "--force" ]]; then
            deploy_sentiment_function
            echo -e "${BLUE}ℹ️ Skipping test (deployment successful)${NC}"
        else
            echo -e "${GREEN}✅ No changes detected${NC}"
        fi
    else
        echo -e "${BLUE}ℹ️ Sentiment-enhanced function not deployed yet. Use manual setup to create it first.${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}🎉 Deployment complete!${NC}"
}

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --force     Force redeploy all functions regardless of changes"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                 # Deploy only changed functions"
    echo "  $0 --force         # Force deploy all functions"
}

# Parse command line arguments
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --force|-f)
        main --force
        ;;
    "")
        main
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        show_help
        exit 1
        ;;
esac