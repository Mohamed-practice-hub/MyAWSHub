param(
    [string]$FunctionName = "tradebot-analysis-java"
)

$ErrorActionPreference = 'Stop'

Write-Host "Running deploy script from" (Get-Location)

Write-Host "Building Maven package..."
mvn clean package -DskipTests

# find shaded jar
$jar = Get-ChildItem -Path .\target\*shade.jar -File -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $jar) {
    Write-Error "Shaded jar not found in target/ (expected *-shade.jar). Check 'target' contents."
    exit 1
}

$awsRegion = $env:AWS_REGION
if (-not $awsRegion) { $awsRegion = 'us-east-1' }

Write-Host "Updating Lambda '$FunctionName' with $($jar.FullName) in region $awsRegion"
aws lambda update-function-code --function-name $FunctionName --zip-file fileb://$($jar.FullName) --region $awsRegion

Write-Host "Deploy finished."