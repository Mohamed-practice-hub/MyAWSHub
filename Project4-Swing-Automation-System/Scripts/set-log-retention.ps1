param(
  [string]$Region = "us-east-1",
  [int]$Days = 30
)
$ErrorActionPreference = 'Stop'
$groups = @(
  "/aws/lambda/swing-webhook-trading",
  "/aws/lambda/swing-portfolio-reporter",
  "/aws/lambda/swing-sentiment-enhanced-lambda",
  "/aws/lambda/swing-performance-analyzer",
  "/aws/lambda/swing-trading-executor",
  "/aws/lambda/swing-trading-test"
)
foreach ($g in $groups) {
  aws logs put-retention-policy --region $Region --log-group-name $g --retention-in-days $Days
  Write-Host "Retention set: $g -> $Days days"
}