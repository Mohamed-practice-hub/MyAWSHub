<#
create-identity-pool.ps1

Creates a Cognito Identity Pool for unauthenticated access, creates an IAM role with minimal DynamoDB read permissions,
and attaches the role to the Identity Pool.

Usage:
  Edit variables below and run:
    .\create-identity-pool.ps1

Prerequisites:
- AWS CLI v2 configured with credentials that can create Cognito Identity Pools and IAM roles.
#>

$REGION = 'us-east-1'
$ACCOUNT = ''  # leave blank to auto-detect
$IDENTITY_POOL_NAME = 'tradebot-dashboard-identity-pool'
$TABLE_NAME = 'tradebot_table'
$ROLE_NAME = 'tradebot-dashboard-unauth-role'

if (-not $ACCOUNT -or $ACCOUNT -eq '') {
  Write-Host "Detecting AWS account ID..."
  try { $ACCOUNT = (aws sts get-caller-identity --query Account --output text).Trim() } catch { Write-Error "Could not detect account ID. Set $ACCOUNT manually."; exit 1 }
  Write-Host "Detected account ID: $ACCOUNT"
}

# 1) Create Identity Pool
Write-Host "Creating Cognito Identity Pool: $IDENTITY_POOL_NAME"
$poolJson = aws cognito-identity create-identity-pool --identity-pool-name $IDENTITY_POOL_NAME --allow-unauthenticated-identities --region $REGION --output json
$IDENTITY_POOL_ID = ($poolJson | ConvertFrom-Json).IdentityPoolId
Write-Host "Created Identity Pool: $IDENTITY_POOL_ID"

# 2) Create IAM role trust policy
$unique = [System.Guid]::NewGuid().ToString()
$trustFile = Join-Path $env:TEMP ("cognito_trust_$unique.json")
$trustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "cognito-identity.amazonaws.com" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
  "StringEquals": { "cognito-identity.amazonaws.com:aud": "${IDENTITY_POOL_ID}" },
        "ForAnyValue:StringLike": { "cognito-identity.amazonaws.com:amr": "unauthenticated" }
      }
    }
  ]
}
"@
$trustPolicy | Out-File -FilePath $trustFile -Encoding ascii

# 3) Create IAM role
Write-Host "Creating IAM role: $ROLE_NAME"
# Capture create-role output (including stderr) to detect errors
$createOutput = aws iam create-role --role-name $ROLE_NAME --assume-role-policy-document file://$trustFile --description "Unauth role for TradeBot dashboard" --region $REGION --output json 2>&1
if ($LASTEXITCODE -eq 0) {
  try {
    $roleJson = $createOutput | ConvertFrom-Json
    $ROLE_ARN = $roleJson.Role.Arn
    Write-Host "Created role ARN: $ROLE_ARN"
    Start-Sleep -Seconds 5
  } catch {
    Write-Warning "Created role but failed to parse output. Will try to fetch existing role ARN."
  }
} else {
  Write-Warning "Create-role returned error: $createOutput"
}

# If creation didn't set ROLE_ARN, attempt to retrieve the existing role ARN with retries
if (-not $ROLE_ARN) {
  $found = $false
  for ($i = 0; $i -lt 6 -and -not $found; $i++) {
    try {
      $getOutput = aws iam get-role --role-name $ROLE_NAME --region $REGION --output json 2>&1
      if ($LASTEXITCODE -eq 0) {
        $roleJson = $getOutput | ConvertFrom-Json
        $ROLE_ARN = $roleJson.Role.Arn
        Write-Host "Found existing role ARN: $ROLE_ARN"
        $found = $true
        break
      } else {
        Write-Warning "get-role attempt $($i+1) failed: $getOutput"
      }
    } catch {
      Write-Warning "get-role attempt $($i+1) raised an exception: $_"
    }
    Start-Sleep -Seconds 2
  }
  if (-not $found) {
    Write-Error "Failed to create or find role $ROLE_NAME"; exit 1
  }
}

# 4) Attach inline policy with minimal DynamoDB read permissions
$policyFile = Join-Path $env:TEMP ("tradebot_ddb_read_policy_$unique.json")
$policy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [ "dynamodb:Query", "dynamodb:GetItem", "dynamodb:Scan" ],
      "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT}:table/${TABLE_NAME}"
    }
  ]
}
"@
$policy | Out-File -FilePath $policyFile -Encoding ascii

aws iam put-role-policy --role-name $ROLE_NAME --policy-name TradeBotDDBReadOnly --policy-document file://$policyFile --region $REGION 2>&1
if ($LASTEXITCODE -eq 0) {
  Write-Host "Attached inline policy TradeBotDDBReadOnly to role $ROLE_NAME"
} else {
  Write-Warning "Failed to attach inline policy. Please inspect IAM and policy file."
}

# Wait for policy to propagate
Start-Sleep -Seconds 3

# 5) Set Identity Pool roles
$roles = @{ "unauthenticated" = $ROLE_ARN }
$rolesJson = $roles | ConvertTo-Json -Compress
if (-not $ROLE_ARN) {
  Write-Error "Role ARN is empty; cannot set identity pool roles. Please check IAM role creation."
  exit 1
}
# Write roles JSON to a temp file and pass as file:// to AWS CLI to avoid quoting issues
$rolesFile = Join-Path $env:TEMP ("identity_pool_roles_$unique.json")
$rolesJson | Out-File -FilePath $rolesFile -Encoding ascii
Write-Host "Setting identity pool roles using file: $rolesFile"
aws cognito-identity set-identity-pool-roles --identity-pool-id $IDENTITY_POOL_ID --roles file://$rolesFile --region $REGION
Write-Host "Set roles for Identity Pool"

# Output for user
Write-Host "Identity Pool ID: $IDENTITY_POOL_ID"
Write-Host "Unauth role ARN: $ROLE_ARN"
Write-Host "Remember to update your dashboard/config.json with the identityPoolId and upload it to your S3 site."

# Save identityPoolId for later scripting
$IDENT_FILE = "$env:TEMP\identity_pool_id.txt"
$IDENTITY_POOL_ID | Out-File -FilePath $IDENT_FILE -Encoding ascii
Write-Host "Saved Identity Pool ID to $IDENT_FILE"
