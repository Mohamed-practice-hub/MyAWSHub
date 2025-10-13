param(
  [string]$Region = "us-east-1",
  [string]$BucketName = ""
)

$ErrorActionPreference = 'Stop'

# Discover account id
$sts = aws sts get-caller-identity | ConvertFrom-Json
$accountId = $sts.Account

if(-not $BucketName){
  $BucketName = "tradeauto-automation-data-$accountId-$Region"
}

Write-Host "Using bucket: $BucketName"

# Create S3 bucket (region-aware)
try {
  if($Region -eq 'us-east-1'){
    aws s3api create-bucket --bucket $BucketName --region $Region | Out-Null
  } else {
    aws s3api create-bucket --bucket $BucketName --create-bucket-configuration LocationConstraint=$Region --region $Region | Out-Null
  }
} catch {
  if($_.Exception.Message -match 'BucketAlreadyOwnedByYou|BucketAlreadyExists'){
    Write-Host "Bucket exists." 
  } else { throw }
}

# Enable versioning
aws s3api put-bucket-versioning --bucket $BucketName --versioning-configuration Status=Enabled --region $Region | Out-Null

# Create Secrets placeholder if not exists (user must fill real values)
$secretName = 'tradeauto-kite/credentials'
try {
  aws secretsmanager describe-secret --secret-id $secretName --region $Region | Out-Null
  Write-Host "Secret $secretName exists"
} catch {
  $tmp = New-TemporaryFile
  $json = @'
{
  "api_key": "",
  "api_secret": "",
  "access_token": "",
  "user_id": "",
  "enctoken": "",
  "refresh_token": ""
}
'@
  Set-Content -Path $tmp -Value $json -Encoding UTF8
  aws secretsmanager create-secret --name $secretName --secret-string file://$tmp --region $Region | Out-Null
  Remove-Item $tmp -Force
  Write-Host "Created secret $secretName (fill values in AWS Console)"
}

# Create basic IAM role for Lambda
$roleName = 'tradeauto-lambda-role'
$trust = @'
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}
  ]
}
'@
$trustFile = New-TemporaryFile
Set-Content -Path $trustFile -Value $trust -Encoding UTF8
try {
  aws iam get-role --role-name $roleName | Out-Null
  Write-Host "Role exists: $roleName"
} catch {
  aws iam create-role --role-name $roleName --assume-role-policy-document file://$trustFile | Out-Null
}

# Attach policies: basic execution + access to Secrets, S3, SES and CloudWatch
aws iam attach-role-policy --role-name $roleName --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole | Out-Null
aws iam attach-role-policy --role-name $roleName --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess | Out-Null
aws iam attach-role-policy --role-name $roleName --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite | Out-Null
aws iam attach-role-policy --role-name $roleName --policy-arn arn:aws:iam::aws:policy/AmazonSESFullAccess | Out-Null

Remove-Item $trustFile -Force

Write-Host "Bootstrap complete. Bucket=$BucketName Role=$roleName Secret=$secretName"
