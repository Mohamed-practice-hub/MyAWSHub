TradeBot Analysis Lambda

This Lambda listens to DynamoDB Streams from the `tradebot_signals_table` and computes technical indicators for updated symbols. It writes the following additional attributes back to the table:

- MA20, MA50, MA200 (Number)
- RSI14 (Number)
- MACD, MACDSignal, MACDHist (Number)
- ATR (Number)
- Signal (String), Confidence (String)
- Notes (String) optionally

Deployment
1) Ensure the table `tradebot_signals_table` has streams enabled (NEW_AND_OLD_IMAGES).
2) Ensure the Lambda role `tradebot-lambda-role` has permission to:
   - dynamodb:Scan, dynamodb:UpdateItem, dynamodb:DescribeTable
   - lambda:InvokeFunction
   - logs:CreateLogGroup/CreateLogStream/PutLogEvents
3) Edit `deploy-analysis-lambda.sh` to set the correct `ROLE_ARN` and run it.

Notes
- This implementation performs a scan to gather history for each symbol; suitable for small to medium datasets.
- For higher throughput or larger datasets, consider storing historical price series in a separate time-series store or using per-symbol indexes and queries.
- The indicator implementations here are simple and approximate; you may replace with more robust libraries if required.

Behavior note:
- The Lambda now checks incoming DynamoDB records and will only compute and write analysis fields that are missing. It will not overwrite existing analysis values. This mirrors the behavior of your fetch lambda which backfills missing data.
 - To prevent re-trigger loops, the Lambda uses DynamoDB's if_not_exists() in the UpdateExpression so existing analysis fields are left unchanged by the analysis Lambda. This avoids creating write events that would retrigger the Lambda indefinitely.
