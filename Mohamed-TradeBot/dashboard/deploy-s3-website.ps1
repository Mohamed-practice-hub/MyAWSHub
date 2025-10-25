<#
deploy-s3-website.ps1

Creates an S3 bucket (prefix 'tradebot-') for hosting the dashboard and uploads the dashboard files.
Requires AWS CLI v2 configured (aws) and PowerShell.

Usage:
  Edit variables below or pass via environment. Then run:
    .\deploy-s3-website.ps1

#>

# --- Configuration (edit or leave blank to auto-detect) ---
$REGION = 'us-east-1'
$ACCOUNT = '<YOUR_ACCOUNT_ID>'   # replace with your AWS account ID, or leave as-is to auto-detect
$BUCKET_NAME = ''                # optional: set full bucket name (must be globally unique)
$BUCKET_PREFIX = 'tradebot'      # bucket name will start with this prefix
$DASHBOARD_DIR = Join-Path $PSScriptRoot '.'

Write-Host "Region: $REGION"

# Auto-detect account ID if not provided
if (-not $ACCOUNT -or $ACCOUNT -eq '<YOUR_ACCOUNT_ID>') {
  Write-Host "Detecting AWS account ID..."
  try {
    $ACCOUNT = (aws sts get-caller-identity --query Account --output text).Trim()
    Write-Host "Detected account ID: $ACCOUNT"
  } catch {
    Write-Error "Failed to detect AWS account ID. Please set the \$ACCOUNT variable at the top of the script and re-run."
    exit 1
  }
}

# Build default bucket name if not set
if (-not $BUCKET_NAME) {
  $timestamp = Get-Date -Format "yyyyMMddHHmmss"
  $BUCKET_NAME = "$BUCKET_PREFIX-$ACCOUNT-dashboard-$timestamp"
}

Write-Host "Target bucket name: $BUCKET_NAME"

# Check if bucket exists
function BucketExists($name) {
  try {
    aws s3api head-bucket --bucket $name --region $REGION > $null 2>&1
    return $true
  } catch {
    return $false
  }
}

if (BucketExists $BUCKET_NAME) {
  Write-Host "Bucket $BUCKET_NAME already exists. Using existing bucket."
} else {
  Write-Host "Creating bucket $BUCKET_NAME in region $REGION..."
  try {
    if ($REGION -eq 'us-east-1') {
      aws s3api create-bucket --bucket $BUCKET_NAME --region $REGION | Out-Null
    } else {
      aws s3api create-bucket --bucket $BUCKET_NAME --region $REGION --create-bucket-configuration LocationConstraint=$REGION | Out-Null
    }
    Write-Host "Created bucket $BUCKET_NAME"
  } catch {
    Write-Warning "Bucket creation failed. Attempting to handle name collisions..."
    # Try a few times with random suffix
    $created = $false
    for ($i=0; $i -lt 5; $i++) {
      $rand = Get-Random -Maximum 100000
      $tryName = "$BUCKET_NAME-$rand"
      Write-Host "Trying bucket name: $tryName"
      try {
        if ($REGION -eq 'us-east-1') { aws s3api create-bucket --bucket $tryName --region $REGION | Out-Null } else { aws s3api create-bucket --bucket $tryName --region $REGION --create-bucket-configuration LocationConstraint=$REGION | Out-Null }
        $BUCKET_NAME = $tryName
        Write-Host "Created bucket $BUCKET_NAME"
        $created = $true
        break
      } catch {
        continue
      }
    }
    if (-not $created) {
      Write-Error "Failed to create a unique bucket. Please pick a different name and try again."
      exit 1
    }
  }
}

# Ensure public access is allowed for the bucket (required for public website)
Write-Host "Disabling S3 public access block for the bucket (if needed)..."
try {
  aws s3api put-public-access-block --bucket $BUCKET_NAME --public-access-block-configuration BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false --region $REGION
  Write-Host "Public access block updated."
} catch {
  Write-Warning "Failed to update public access block. You may need to adjust account-level public access settings in the AWS Console."
}

# Set website configuration
Write-Host "Configuring bucket as a static website..."
try {
  aws s3 website s3://$BUCKET_NAME/ --index-document index.html --error-document index.html
  Write-Host "Website configured."
} catch {
  Write-Warning "Failed to configure bucket website."
}

# Set bucket policy to allow public read of objects
$policy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::$BUCKET_NAME/*"]
    }
  ]
}
"@

$policyFile = Join-Path $env:TEMP "s3_policy_$($BUCKET_NAME).json"
$policy | Out-File -FilePath $policyFile -Encoding utf8
try {
  aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file://$policyFile --region $REGION
  Write-Host "Bucket policy applied to allow public read."
} catch {
  Write-Warning "Failed to apply bucket policy. You may need to apply it manually in the Console."
}

# Sync dashboard files
Write-Host "Uploading dashboard files from $DASHBOARD_DIR to s3://$BUCKET_NAME/ ..."
try {
  aws s3 sync $DASHBOARD_DIR s3://$BUCKET_NAME/ --acl public-read --region $REGION
  Write-Host "Upload complete."
} catch {
  Write-Error "Failed to sync files to S3."
  exit 1
}

# Output website URL
$websiteUrl = "http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"
Write-Host "Website deployed: $websiteUrl"
Write-Host "If you want HTTPS, configure CloudFront in front of the bucket."

# Print the bucket name and account ID (exposed as variables)
Write-Host "Done. Use the following variables in your scripts or config.json:"
Write-Host "`$ACCOUNT = $ACCOUNT"
Write-Host "`$BUCKET_NAME = $BUCKET_NAME"
