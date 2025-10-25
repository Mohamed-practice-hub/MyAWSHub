# autotrade-kite-token-refresher (container image Lambda)

Automates daily Zerodha login with Playwright + TOTP and writes the `access_token` back into your existing secret (default: `autotrade-kite/credentials`).

## Secret schema

Store these fields in AWS Secrets Manager under `autotrade-kite/credentials` (or set `SECRET_NAME` env var):

{
  "api_key": "...",            // required (aka KITE_API_KEY)
  "api_secret": "...",         // required (aka KITE_API_SECRET)
  "username": "...",           // required (aka user_id)
  "password": "...",           // required
  "totp_secret": "...",        // recommended (for 2FA)
  "pin": "...."                // optional fallback if your account uses PIN 2FA
}

On success, the Lambda updates the same secret with:

{
  "access_token": "...",
  "user_id": "...",
  "last_refreshed_ts": 1699999999
}

## Build and deploy (ECR + Lambda)

1) Create an ECR repo once (replace account/region as needed):

```powershell
$ACCOUNT=(aws sts get-caller-identity --query Account --output text)
$REGION="us-east-1"
$REPO="autotrade-kite-token-refresher"
aws ecr create-repository --repository-name $REPO 2>$null
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
```

2) Build and push image (run from this folder):

```powershell
$IMG="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest"
docker build -t $IMG .
docker push $IMG
```

3) Create/Update the Lambda using the container image:

```powershell
$ROLE_ARN=(aws iam get-role --role-name autotrade-lambda-role --query Role.Arn --output text)
$FUNC="autotrade-kite-token-refresher"

aws lambda create-function `
  --function-name $FUNC `
  --package-type Image `
  --code ImageUri=$IMG `
  --role $ROLE_ARN `
  --timeout 120 `
  --memory-size 1024 2>$null | Out-Null

aws lambda update-function-configuration `
  --function-name $FUNC `
  --environment Variables="{SECRET_NAME=autotrade-kite/credentials}"

aws lambda wait function-active-v2 --function-name $FUNC
```

## Schedule daily (EventBridge)

EventBridge uses UTC. 08:45 AM IST is 03:15 UTC. The rule below triggers at 03:15 UTC daily (≈11:15 PM Toronto during EDT).

```powershell
$RULE="autotrade-kite-token-refresh-daily"
aws events put-rule --name $RULE --schedule-expression "cron(15 3 ? * * *)" --state ENABLED
$FN_ARN=(aws lambda get-function --function-name autotrade-kite-token-refresher --query Configuration.FunctionArn --output text)
$RULE_ARN=(aws events describe-rule --name $RULE --query Arn --output text)
aws lambda add-permission --function-name autotrade-kite-token-refresher --statement-id evt-$(Get-Random) --action lambda:InvokeFunction --principal events.amazonaws.com --source-arn $RULE_ARN
aws events put-targets --rule $RULE --targets Id="1",Arn="$FN_ARN"
```

## Notes
- Container image avoids native dependency issues for Playwright.
- If your account enforces TOTP, set `totp_secret` (from your Authenticator seed). If you only have PIN 2FA, set `pin`.
- Logs in CloudWatch will show success or failure; do not print secrets.
- Trading Lambdas continue to read `access_token` from the same secret and work unchanged.
