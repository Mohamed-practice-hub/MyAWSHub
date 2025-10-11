#!/bin/bash
# File watcher script that automatically deploys when Lambda code changes

LAMBDA_DIR="../Lambda"
DEPLOY_SCRIPT="./deploy-lambda.sh"

echo "🔍 Watching Lambda directory for changes..."
echo "Press Ctrl+C to stop"

# Function to get file modification times
get_file_times() {
    find "$LAMBDA_DIR" -name "*.py" -exec stat -c %Y {} \; 2>/dev/null | sort -n | tail -1
}

# Initial state
last_modified=$(get_file_times)

while true; do
    sleep 5
    current_modified=$(get_file_times)
    
    if [[ "$current_modified" != "$last_modified" ]]; then
        echo "📝 Changes detected! Deploying..."
        bash "$DEPLOY_SCRIPT"
        last_modified=$current_modified
        echo "✅ Watching resumed..."
    fi
done