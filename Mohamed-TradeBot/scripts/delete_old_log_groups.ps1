# Deletes CloudWatch log groups with no events in the last N days (or never had events)
# Usage: run in PowerShell in this workspace. Region is set to us-east-1 by default.

param(
    [int]$Days = 10,
    [string]$Region = 'us-east-1',
    [switch]$DryRun
)

$cutoff = (Get-Date).ToUniversalTime().AddDays(-$Days)
$cutoffMs = [long]($cutoff.Subtract([datetime]'1970-01-01').TotalMilliseconds)

Write-Output "Cutoff date (UTC): $cutoff  -- cutoff ms: $cutoffMs"

# Get all log groups
$lgJson = aws logs describe-log-groups --region $Region --output json
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to list log groups (aws CLI exit $LASTEXITCODE)"; exit 1 }
$groups = $lgJson | ConvertFrom-Json

$deleted = @()
$kept = @()

foreach ($g in $groups.logGroups) {
    $name = $g.logGroupName
    # Get latest event timestamp from log streams
    $lsJson = aws logs describe-log-streams --region $Region --log-group-name "$name" --order-by LastEventTime --descending --limit 1 --output json
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Failed to describe log streams for $name (aws exit $LASTEXITCODE) - skipping"
        $kept += $name
        continue
    }
    $ls = $lsJson | ConvertFrom-Json
    $lastEvent = $null
    if ($ls.logStreams -and $ls.logStreams.Count -gt 0) {
        $lastEvent = $ls.logStreams[0].lastEventTimestamp
    }
    # If no lastEvent, fall back to creationTime
    if (-not $lastEvent) { $lastEvent = $g.creationTime }
    # Compare
    if ([long]$lastEvent -lt $cutoffMs) {
        Write-Output "Deleting: $name  (lastEvent/creation ms: $lastEvent)"
        if (-not $DryRun) {
            aws logs delete-log-group --region $Region --log-group-name "$name"
            if ($LASTEXITCODE -eq 0) {
                $deleted += $name
            } else {
                Write-Warning "Failed to delete $name (aws exit $LASTEXITCODE)"
                $kept += $name
            }
        } else {
            $deleted += $name
        }
    } else {
        $kept += $name
    }
}

Write-Output "\nSummary: deleted=$($deleted.Count), kept=$($kept.Count)"
if ($deleted.Count -gt 0) { Write-Output "Deleted groups:"; $deleted | ForEach-Object { Write-Output "  $_" } }
if ($kept.Count -gt 0) { Write-Output "Kept groups (recent or errored):"; $kept | ForEach-Object { Write-Output "  $_" } }
