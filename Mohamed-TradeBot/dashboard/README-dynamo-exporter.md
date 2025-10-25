DynamoDB Stream -> S3 Exporter

This lambda listens to DynamoDB Streams and writes a full snapshot of the `tradebot_table` to S3 `data.json` on each update.

When to use
- Small tables where a full snapshot is acceptable and you want near-real-time updates on changes.

Files
- `lambda/dynamodb_stream_to_s3.py` - the Lambda handler.
- `deploy-dynamo-exporter.sh` - packaging and deployment script (requires AWS CLI and permissions).

Setup
1) Ensure your DynamoDB table has streams enabled (NEW_AND_OLD_IMAGES).
2) Ensure you have an IAM role for the Lambda (`tradebot-lambda-role`) with policies:
   - AmazonDynamoDBFullAccess (or minimal stream read)
   - AmazonS3FullAccess (or minimal s3:PutObject on the target bucket)
3) Edit `deploy-dynamo-exporter.sh` to set the correct `ROLE_ARN`, `DDB_TABLE`, and `S3_BUCKET`.
4) Run `./deploy-dynamo-exporter.sh` to create/update the Lambda and event source mapping.

Notes
- The Lambda does a full scan of the table on each stream invocation. This is fine for small tables but costly for large tables. Consider incremental writes if needed.
- Make sure the Lambda role has permissions for dynamodb:DescribeTable (to read stream ARN) and dynamodb:Scan if using this code.
- The Lambda writes `data.json` to S3; the dashboard loads this file as its source when configured.
