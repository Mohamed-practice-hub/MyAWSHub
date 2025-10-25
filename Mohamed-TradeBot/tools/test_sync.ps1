param(
  [string]$Symbol = "TEST_SYNC",
  [string]$TableName = "tradebot_signals_table",
  [int]$Open = 100,
  [int]$High = 110,
  [int]$Low = 90,
  [int]$Close = 105,
  [int]$Volume = 1000
)

$now = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$tradedDate = (Get-Date).ToString('yyyy-MM-dd')
$body = @{
  SymbolKey = @{ S = $Symbol }
  TradedDate = @{ S = $tradedDate }
  Open = @{ N = "$Open" }
  High = @{ N = "$High" }
  Low = @{ N = "$Low" }
  Close = @{ N = "$Close" }
  Volume = @{ N = "$Volume" }
  Timestamp = @{ S = $now }
}

$tf = "tmp_test_sync_item.json"
$body | ConvertTo-Json -Depth 5 | Set-Content -Path $tf -Encoding utf8

aws dynamodb put-item --table-name $TableName --item file://$tf --region us-east-1
Write-Host "Inserted test item for $Symbol with TradedDate $tradedDate and Timestamp $now"
Remove-Item $tf -ErrorAction SilentlyContinue
