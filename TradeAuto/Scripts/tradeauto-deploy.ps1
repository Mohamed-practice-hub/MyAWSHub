param(
  [string]$Region = "us-east-1",
  [string]$RoleName = "tradeauto-lambda-role",
  [string]$BucketName = "",
  [string]$SesFrom = "",
  [string]$SesTo = ""
)
$ErrorActionPreference = 'Stop'

$sts = aws sts get-caller-identity | ConvertFrom-Json
$accountId = $sts.Account
if(-not $BucketName){ $BucketName = "tradeauto-automation-data-$accountId-$Region" }

# Resolve role ARN
$roleArn = (aws iam get-role --role-name $RoleName | ConvertFrom-Json).Role.Arn

# Helper to zip a lambda folder with src and site-packages
function New-LambdaZip($lambdaDir, $zipOut){
  if(Test-Path $zipOut){ Remove-Item $zipOut -Force }
  $tmp = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName())
  New-Item -ItemType Directory -Path $tmp | Out-Null
  # copy lambda code
  Copy-Item -Recurse -Force -Path (Join-Path $lambdaDir '*') -Destination $tmp
  # copy src
  Copy-Item -Recurse -Force -Path (Join-Path $PSScriptRoot '..' 'src') -Destination (Join-Path $tmp 'src')
  # install deps
  $req = Join-Path (Split-Path $PSScriptRoot -Parent) 'requirements.txt'
  $site = Join-Path $tmp 'python'
  New-Item -ItemType Directory -Path $site | Out-Null
  python -m pip install -r $req -t $site | Out-Null
  # move deps up (flatten)
  Get-ChildItem -Path $site | Move-Item -Destination $tmp
  Remove-Item $site -Force -Recurse
  # zip
  Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath $zipOut -Force
  Remove-Item $tmp -Recurse -Force
}

$envMap = @{ 
  KITE_SECRET_NAME = 'tradeauto-kite/credentials';
  S3_BUCKET = $BucketName;
  SES_FROM = $SesFrom;
  SES_TO = $SesTo;
  AUTO_EXECUTE = 'false';
  DEBOUNCE_SECONDS = '30';
  MIN_INTERVAL_SAME_SYMBOL_SECONDS = '300';
  MAX_TRADES_PER_DAY = '20';
}

# Deploy webhook trading
$webDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'lambdas' 'webhook-trading'
$webZip = Join-Path $env:TEMP "tradeauto-webhook-trading.zip"
New-LambdaZip -lambdaDir $webDir -zipOut $webZip
$webName = 'tradeauto-webhook-trading'
try{ aws lambda get-function --function-name $webName | Out-Null } catch { 
  aws lambda create-function --function-name $webName --runtime python3.11 --role $roleArn --timeout 30 --handler lambda_function.lambda_handler --zip-file fileb://$webZip --region $Region | Out-Null
}
aws lambda update-function-code --function-name $webName --zip-file fileb://$webZip --region $Region | Out-Null
${envJson} = ($envMap | ConvertTo-Json -Compress)
aws lambda update-function-configuration --function-name $webName --region $Region --environment "Variables=$envJson" | Out-Null

# Deploy portfolio reporter
$porDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'lambdas' 'portfolio-reporter'
$porZip = Join-Path $env:TEMP "tradeauto-portfolio-reporter.zip"
New-LambdaZip -lambdaDir $porDir -zipOut $porZip
$porName = 'tradeauto-portfolio-reporter'
try{ aws lambda get-function --function-name $porName | Out-Null } catch { 
  aws lambda create-function --function-name $porName --runtime python3.11 --role $roleArn --timeout 30 --handler lambda_function.lambda_handler --zip-file fileb://$porZip --region $Region | Out-Null
}
aws lambda update-function-code --function-name $porName --zip-file fileb://$porZip --region $Region | Out-Null
${envJson} = ($envMap | ConvertTo-Json -Compress)
aws lambda update-function-configuration --function-name $porName --region $Region --environment "Variables=$envJson" | Out-Null

# Deploy history api
$hisDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'lambdas' 'history-api'
$hisZip = Join-Path $env:TEMP "tradeauto-history-api.zip"
New-LambdaZip -lambdaDir $hisDir -zipOut $hisZip
$hisName = 'tradeauto-history-api'
try{ aws lambda get-function --function-name $hisName | Out-Null } catch { 
  aws lambda create-function --function-name $hisName --runtime python3.11 --role $roleArn --timeout 30 --handler lambda_function.lambda_handler --zip-file fileb://$hisZip --region $Region | Out-Null
}
aws lambda update-function-code --function-name $hisName --zip-file fileb://$hisZip --region $Region | Out-Null
${envJson} = ($envMap | ConvertTo-Json -Compress)
aws lambda update-function-configuration --function-name $hisName --region $Region --environment "Variables=$envJson" | Out-Null

# Enable Function URL for history api
try{
  aws lambda get-function-url-config --function-name $hisName --region $Region | Out-Null
} catch {
  aws lambda create-function-url-config --function-name $hisName --auth-type NONE --cors "AllowedOrigins=[*],AllowedMethods=[GET,OPTIONS]" --region $Region | Out-Null
}
# Add permission for URL
try{
  aws lambda add-permission --function-name $hisName --statement-id tradeauto-url --action lambda:InvokeFunctionUrl --principal '*' --function-url-auth-type NONE --region $Region | Out-Null
} catch { }

Write-Host "Deployed Lambdas: $webName, $porName, $hisName"
