# TradeAuto

TradeAuto is a fresh, minimal, AWS-native trading automation starter that integrates with Zerodha Kite Connect. It replaces the older Project4 Alpaca setup and uses resource names starting with "tradeauto". No GPT/LLM code is included in any AWS service.

## Components
- Lambda: tradeauto-webhook-trading — receives webhook signals and (optionally) places orders via Zerodha Kite.
- Lambda: tradeauto-portfolio-reporter — sends a daily email summary of positions/holdings.
- Lambda: tradeauto-history-api — exposes last-30-days order history via a Function URL with CORS.
- S3: tradeauto automation bucket (logs/guardrails/history artifacts; name templated with account/region).
- Website: static history dashboard (optional S3 website hosting) to view 30-day history table.
- CloudWatch: dashboard, logs, and EventBridge schedules (optional).

## Naming
All AWS resources created by scripts start with prefix: tradeauto-

## Requirements
- AWS CLI configured with your account and region.
- PowerShell 5+ (Windows) or PowerShell 7.
- Python 3.11+ locally for packaging.
- Zerodha Kite Connect API key/secret and a valid access_token.

Note on Kite tokens: Access tokens expire daily. These scripts expect you to provide an access_token (and optionally refresh_token if your plan supports it). See "Kite credentials" below.

## Quick start
1) Bootstrap IAM, S3, and Secrets (one-time):

   Run, replacing -Region if needed.

   - PowerShell:
     ./Scripts/tradeauto-bootstrap.ps1 -Region us-east-1

2) Package and deploy the three Lambdas:

   - PowerShell:
     ./Scripts/tradeauto-deploy.ps1 -Region us-east-1

3) (Optional) Enable Function URL for history API and upload the static site:

   - PowerShell:
     ./Scripts/tradeauto-deploy-history-site.ps1 -Region us-east-1

4) Test
- Invoke history API Function URL in a browser. You should see JSON with last 30 days of orders.
- Open the static site (if uploaded) and verify the table renders.

## Kite credentials
Create a JSON secret in AWS Secrets Manager with name: tradeauto-kite/credentials

Example secret value:
{
  "api_key": "your_kite_api_key",
  "api_secret": "your_kite_api_secret",
  "access_token": "your_current_access_token",
  "user_id": "AB1234",
  "enctoken": "optional_if_you_use_cookie_method",
  "refresh_token": "optional_if_enabled"
}

By default, Lambdas read secret name from env KITE_SECRET_NAME (default: tradeauto-kite/credentials).

## Environment variables
Common for Lambdas:
- KITE_SECRET_NAME: tradeauto-kite/credentials
- S3_BUCKET: tradeauto-automation-data-<accountId>-<region>
- SES_FROM: you@example.com (must be verified in SES)
- SES_TO: you@example.com (comma-separated allowed)
- AUTO_EXECUTE: true|false (webhook: whether to actually place orders)
- DEBOUNCE_SECONDS: e.g., 30
- MIN_INTERVAL_SAME_SYMBOL_SECONDS: e.g., 300
- MAX_TRADES_PER_DAY: e.g., 20

## Local packaging notes
- These scripts package dependencies (kiteconnect and its deps) into each Lambda zip. boto3 is excluded (present in Lambda runtime).

## Teardown old Project4
Use the provided script to optionally delete Project4 (swing-*) resources. By default it runs in DryRun mode.

- PowerShell:
  ./Scripts/teardown-project4.ps1 -Region us-east-1 -Apply:$false

## Security
- Secrets are pulled at runtime; avoid logging secrets.
- CORS for Function URL is restricted to the site origin you set in Scripts.

## Troubleshooting
- Missing or expired access token: update your Secrets Manager secret and redeploy env vars if needed.
- 403 or 500 from history API: check CloudWatch Logs for tradeauto-history-api.
- Zipping failures on Windows: ensure no process is locking the zip; scripts write to temp first.
