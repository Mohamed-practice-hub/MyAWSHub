<#
cleanup-old-api.ps1

Safely archive/remove old API-related artifacts in the dashboard folder.
This script will move files to a local 'archive' folder rather than permanently delete them.
#>

$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent
$archiveDir = Join-Path $scriptDir 'archive_$(Get-Date -Format yyyyMMddHHmmss)'
New-Item -Path $archiveDir -ItemType Directory | Out-Null

# List of patterns/files to archive
$paths = @(
  'deploy-dashboard-api-v1.sh',
  'lambda/dynamodb_api_v1.py',
  'dynamodb_api_v1.zip',
  'config.json.sample' # keep the sample? you can adjust
)

foreach ($p in $paths) {
  $full = Join-Path $scriptDir $p
  if (Test-Path $full) {
    $dest = Join-Path $archiveDir (Split-Path $p -Leaf)
    Move-Item -Path $full -Destination $dest -Force
    Write-Host "Archived $p -> $dest"
  } else {
    Write-Host "Not found: $p"
  }
}

Write-Host "Cleanup complete. Files moved to $archiveDir"
