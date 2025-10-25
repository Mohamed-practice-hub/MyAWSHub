# Deploy EventBridge schedule to invoke fetch Lambda every 10 minutes with a fixed payload
# Usage: Open PowerShell, cd to this script folder and run: .\deploy-schedule.ps1
# Requires: AWS CLI configured for an identity with permissions to create EventBridge rules, put-targets, and add Lambda permission.

param(
    [string]$LambdaName = 'tradebot_fetch_lambda',
    [string]$RuleName = 'tradebot-fetch-schedule-10min',
    [string]$Region = 'us-east-1'
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$payloadFile = Join-Path $scriptDir 'schedule_payload.json'
if (-not (Test-Path $payloadFile)) {
    Write-Error "Payload file not found: $payloadFile"
    exit 1
}

# Get AWS account id
$account = aws sts get-caller-identity --query Account --output text --region ${Region}
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to get AWS account id"; exit 2 }
$lambdaArn = "arn:aws:lambda:${Region}:${account}:function:${LambdaName}"

Write-Host "Creating/updating EventBridge rule '$RuleName' (rate(10 minutes)) in $Region ..."
aws events put-rule --name $RuleName --schedule-expression "rate(10 minutes)" --state ENABLED --region $Region | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create rule"; exit 3 }

# Add permission for EventBridge to invoke the Lambda (idempotent if statement-id exists)
$statementId = "AllowEventBridgeInvoke-$RuleName"
try {
    Write-Host "Adding Lambda permission (if absent) ..."
    $sourceArn = "arn:aws:events:${Region}:${account}:rule/${RuleName}"
    aws lambda add-permission --function-name ${LambdaName} --statement-id ${statementId} --action "lambda:InvokeFunction" --principal events.amazonaws.com --source-arn $sourceArn --region ${Region} | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "add-permission returned non-zero (it may already exist). Continuing..."
    }
} catch {
    Write-Warning "add-permission may have failed or already exists: $_"
}

# Read payload and escape for embedding into targets JSON
$rawPayload = Get-Content -Raw -Path $payloadFile
# Ensure the payload is valid JSON
try {
    $null = $rawPayload | ConvertFrom-Json
} catch {
    Write-Error "Payload file is not valid JSON: $_"
    exit 4
}

# Build targets JSON safely using ConvertTo-Json so quoting/escaping is handled correctly
$targetObj = @(@{ Id = '1'; Arn = $lambdaArn; Input = $rawPayload })
$targetsJson = $targetObj | ConvertTo-Json -Depth 10
$tmpTargets = Join-Path $scriptDir 'targets.tmp.json'
Set-Content -Path $tmpTargets -Value $targetsJson -Encoding UTF8

Write-Host "Putting target to rule..."
aws events put-targets --rule $RuleName --targets file://$tmpTargets --region $Region | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to put targets"; Remove-Item -Force $tmpTargets; exit 5 }

Remove-Item -Force $tmpTargets
Write-Host "Schedule created: rule='$RuleName' -> Lambda='$LambdaName' every 10 minutes."
Write-Host "You can verify with: aws events list-targets-by-rule --rule $RuleName --region $Region"
Write-Host "And check CloudWatch Logs for /aws/lambda/$LambdaName after the next run."