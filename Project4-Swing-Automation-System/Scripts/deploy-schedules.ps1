param(
  [string]$Region = "us-east-1"
)
$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot/..\.." | Out-Null
$rules = Get-Content -Raw -Encoding UTF8 "Project4-Swing-Automation-System/deployment/eventbridge-schedules.json" | ConvertFrom-Json
foreach ($r in $rules.Rules) {
  $name = $r.Name
  $expr = $r.ScheduleExpression
  $state = $r.State
  aws events put-rule --region $Region --name $name --schedule-expression $expr --state $state | Out-Null
  foreach ($t in $r.Targets) {
    $targetId = $t.Id
    $arn = $t.Arn
    aws events put-targets --region $Region --rule $name --targets "Id=$targetId,Arn=$arn" | Out-Null
    # Ensure EventBridge can invoke the function
    try {
      $sid = "evt-" + $name + "-" + $targetId
      aws lambda add-permission --region $Region --function-name $arn --statement-id $sid --action lambda:InvokeFunction --principal events.amazonaws.com --source-arn (aws events describe-rule --region $Region --name $name --query Arn --output text) | Out-Null
    } catch {
      # Likely already exists; ignore
    }
  }
  Write-Host "Upserted rule: $name ($expr)"
}
Write-Host "EventBridge schedules deployed."