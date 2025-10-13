param(
  [string]$Region = "us-east-1",
  [switch]$Apply
)
$ErrorActionPreference = 'Stop'

$prefix = 'swing-'

function Remove-IfExists($type, $name, $script){
  try {
    & $script
    Write-Host "Removed $type $name"
  } catch {
    if($_.Exception.Message -match 'ResourceNotFoundException|NotFound|does not exist'){
      Write-Host "$type $name not found"
    } else { throw }
  }
}

if(-not $Apply){
  Write-Host "DryRun mode. Use -Apply to actually delete."
}

# Lambdas
$lamNames = @('swing-webhook-trading','swing-portfolio-reporter')
foreach($n in $lamNames){
  if($Apply){ Remove-IfExists 'Lambda' $n { aws lambda delete-function --function-name $n --region $Region } }
}

# EventBridge rules
$rules = @('swing-lightcheck-15m','swing-daily-heavy')
foreach($r in $rules){
  try{
    $targets = aws events list-targets-by-rule --rule $r --region $Region | ConvertFrom-Json
    foreach($t in $targets.Targets){ if($Apply){ aws events remove-targets --rule $r --ids $t.Id --region $Region | Out-Null } }
    if($Apply){ aws events delete-rule --name $r --region $Region | Out-Null }
    Write-Host "Processed rule $r"
  } catch { Write-Host "Rule $r missing" }
}

# Log groups
$logs = aws logs describe-log-groups --log-group-name-prefix '/aws/lambda/swing-' --region $Region | ConvertFrom-Json
foreach($lg in $logs.logGroups){ if($Apply){ aws logs delete-log-group --log-group-name $lg.logGroupName --region $Region | Out-Null } }

Write-Host "Project4 teardown complete (Apply=$Apply)"
