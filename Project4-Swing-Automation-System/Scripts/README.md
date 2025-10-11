# Lambda Auto-Deployment Scripts

Automated deployment scripts for Swing Trading Lambda functions.

## Scripts Overview

### 1. `deploy-lambda.sh` - Main Deployment Script
**Purpose**: Detects code changes and deploys only modified Lambda functions

**Features**:
- ✅ Change detection using SHA256 hashes
- ✅ Automatic packaging with dependencies
- ✅ Function testing after deployment
- ✅ Color-coded output for easy reading
- ✅ Force deployment option
- ✅ Error handling and cleanup

**Usage**:
```bash
# Deploy only changed functions
./deploy-lambda.sh

# Force deploy all functions
./deploy-lambda.sh --force

# Show help
./deploy-lambda.sh --help
```

### 2. `deploy-lambda.bat` - Windows Wrapper
**Purpose**: Run deployment from Windows Command Prompt

**Usage**:
```cmd
# From Windows Command Prompt
deploy-lambda.bat

# With force option
deploy-lambda.bat --force
```

### 3. `watch-and-deploy.sh` - File Watcher
**Purpose**: Continuously monitor Lambda code and auto-deploy on changes

**Usage**:
```bash
# Start watching (runs until Ctrl+C)
./watch-and-deploy.sh
```

## Quick Start

### Option 1: Manual Deployment
```bash
cd Scripts
./deploy-lambda.sh
```

### Option 2: Continuous Watching
```bash
cd Scripts
./watch-and-deploy.sh
```

### Option 3: Windows Users
```cmd
cd Scripts
deploy-lambda.bat
```

## How It Works

1. **Change Detection**: Compares SHA256 hashes of deployed vs local code
2. **Smart Packaging**: Only includes necessary dependencies per function
3. **Automatic Testing**: Runs test payload after each deployment
4. **Error Handling**: Graceful failure with cleanup

## Supported Functions

- ✅ `swing-automation-data-processor-lambda` (Main trading bot)
- ✅ `swing-performance-analyzer` (Performance analysis)
- ✅ `swing-sentiment-enhanced-lambda` (Sentiment analysis - optional)

## Prerequisites

- AWS CLI configured with appropriate permissions
- Git Bash (for Windows users)
- Lambda functions already created (use manual setup guide first)

## Troubleshooting

### "Function not found" error
- Ensure Lambda functions are created using the manual setup guide first
- Check AWS CLI credentials and region

### "Permission denied" error
- Make scripts executable: `chmod +x *.sh`
- Verify IAM permissions for Lambda updates

### "Dependencies not found" error
- Run from Scripts directory: `cd Scripts`
- Ensure Lambda directory structure is correct

## Integration with Development Workflow

### Git Hook Integration
Add to `.git/hooks/post-commit`:
```bash
#!/bin/bash
cd Scripts
./deploy-lambda.sh
```

### VS Code Integration
Add to `.vscode/tasks.json`:
```json
{
    "label": "Deploy Lambda",
    "type": "shell",
    "command": "./Scripts/deploy-lambda.sh",
    "group": "build"
}
```