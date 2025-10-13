# Hybrid Schedule Plan (No GPT in AWS)

This adds two EventBridge rules:
- swing-lightcheck-15m: Every 15 minutes during market hours (UTC 14-20), trigger a lightweight check.
- swing-daily-heavy: Once daily at 13:45 UTC for full analysis.

You must replace ACCOUNT_ID in `deployment/eventbridge-schedules.json` and then create rules via CLI or console.

Also apply S3 lifecycle rules in `deployment/s3-lifecycle-rules.json` to the bucket and set CloudWatch Logs retention to 30 days.

No GPT or LLM settings are added to Lambda.
