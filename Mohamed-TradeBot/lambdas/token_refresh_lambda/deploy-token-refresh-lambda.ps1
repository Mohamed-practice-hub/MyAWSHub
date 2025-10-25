$functionName = 'autotrade-kite-token-refresh-daily'
$roleArn = 'arn:aws:iam::206055866143:role/tradebot-lambda-role'  # update if different
$zip = '..\token_refresh_lambda.zip'
if(Test-Path $zip){ Remove-Item $zip -Force }
Set-Location $PSScriptRoot
Compress-Archive -Path token_refresh_lambda.py -DestinationPath $zip -Force
Write-Host "Created $zip"
# Find layer arn from known name
$layerArn = 'arn:aws:lambda:us-east-1:206055866143:layer:autotrade-kiteconnect-py311:2'
try{
    aws lambda create-function --function-name $functionName --runtime python3.11 --role $roleArn --handler token_refresh_lambda.lambda_handler --zip-file fileb://$zip --region us-east-1 --layers $layerArn --environment Variables={SECRET_NAME=autotrade-kite/credentials,TELEGRAM_BOT_TOKEN='',TELEGRAM_CHAT_ID=''}
}catch{
    Write-Host 'Create failed, trying update'
    aws lambda update-function-code --function-name $functionName --zip-file fileb://$zip --region us-east-1
    aws lambda update-function-configuration --function-name $functionName --layers $layerArn --environment Variables={SECRET_NAME=autotrade-kite/credentials,TELEGRAM_BOT_TOKEN='',TELEGRAM_CHAT_ID=''} --region us-east-1
}
aws lambda get-function-configuration --function-name $functionName --region us-east-1 --query '{FunctionName:FunctionName,LastModified:LastModified,State:State}' --output json
