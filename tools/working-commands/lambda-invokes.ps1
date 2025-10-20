# Working commands for Lambda invokes (PowerShell / AWS CLI)
# Always prefer these patterns to avoid JSON quoting issues in Windows PowerShell 5.1.

# Invoke history fetcher: backfill N days for a symbol, direct S3 write
# Usage: set $symbol and $days, then run.
param(
  [string]$Region = 'us-east-1',
  [string]$FunctionName = 'autotrade-history-fetch-daily'
)

function Invoke-BackfillDays([string]$symbol, [int]$days){
  $tmp = New-TemporaryFile
  $json = '{"symbol":"' + $symbol + '","days":' + $days + ',"direct":true}'
  Set-Content -Path $tmp -Value $json -Encoding ascii
  aws lambda invoke --function-name $FunctionName --region $Region --cli-binary-format raw-in-base64-out --no-cli-pager --payload fileb://$tmp out-$($symbol -replace ':','-').json | Out-Null
  $resp = Get-Content out-$($symbol -replace ':','-').json | ConvertFrom-Json
  $body = $resp.body | ConvertFrom-Json
  return $body
}

# Example:
# $r = Invoke-BackfillDays -symbol 'NSE:INFY' -days 400
# Write-Host ("INFY -> dates=$($r.dates) written=$($r.written) skipped=$($r.skipped)")
