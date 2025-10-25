<#
create-s3-bucket.ps1

Creates a globally-unique S3 bucket prefixed with 'tradebot' and prints its name.

Usage:
  Edit variables at the top (or rely on defaults) and run the script in PowerShell.

Prerequisites:
- AWS CLI v2 installed and configured for an account with permission to create S3 buckets.
#>

# --- Configuration ---
$REGION = 'us-east-1'
$ACCOUNT = ''  # Leave blank to auto-detect
$BUCKET_PREFIX = 'tradebot'  # prefix of bucket
$SUFFIX = 'dashboard'

# Auto-detect account ID if not provided
if (-not $ACCOUNT -or $ACCOUNT -eq '') {
  Write-Host "Detecting AWS account ID..."
  try {
    $ACCOUNT = (aws sts get-caller-identity --query Account --output text).Trim()
    Write-Host "Detected account ID: $ACCOUNT"
  } catch {
    Write-Error "Failed to detect AWS account ID. Please set the `$ACCOUNT variable and try again."
    exit 1
  }
}

# Generate a meaningful default bucket name (can be overridden by setting $BUCKET_NAME)
if (-not $BUCKET_NAME -or $BUCKET_NAME -eq '') {
  # Default: tradebot-<account>-dashboard
  $BUCKET_NAME = "$BUCKET_PREFIX-$ACCOUNT-$SUFFIX"
} else {
  Write-Host "Using provided bucket name: $BUCKET_NAME"
}
Write-Host "Attempting to create bucket: $BUCKET_NAME in region $REGION"

# Create bucket (handle us-east-1 specially)
try {
  if ($REGION -eq 'us-east-1') {
    aws s3api create-bucket --bucket $BUCKET_NAME --region $REGION | Out-Null
  } else {
    aws s3api create-bucket --bucket $BUCKET_NAME --region $REGION --create-bucket-configuration LocationConstraint=$REGION | Out-Null
  }
  Write-Host "Bucket created successfully: $BUCKET_NAME"
} catch {
  Write-Warning "Bucket creation failed. Attempting alternative names..."
  $created = $false
  for ($i=0; $i -lt 10; $i++) {
    $rand = Get-Random -Maximum 100000
    $tryName = "$BUCKET_PREFIX-$ACCOUNT-$SUFFIX-$rand"
    Write-Host "Trying bucket: $tryName"
    try {
      if ($REGION -eq 'us-east-1') {
        aws s3api create-bucket --bucket $tryName --region $REGION | Out-Null
      } else {
        aws s3api create-bucket --bucket $tryName --region $REGION --create-bucket-configuration LocationConstraint=$REGION | Out-Null
      }
      $BUCKET_NAME = $tryName
      Write-Host "Bucket created successfully: $BUCKET_NAME"
      $created = $true
      break
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  if (-not $created) {
    Write-Error "Failed to create a unique bucket. Please choose a different prefix or bucket name and try again."
    exit 1
  }
}

# Output the result
Write-Host "Created bucket: $BUCKET_NAME"
Write-Host "Use this bucket for hosting the dashboard or uploading config.json."

# Print to stdout for scripting
"$BUCKET_NAME" | Out-File -FilePath "$env:TEMP\created_bucket_name.txt" -Encoding ascii
Write-Host "Saved bucket name to $env:TEMP\created_bucket_name.txt"
