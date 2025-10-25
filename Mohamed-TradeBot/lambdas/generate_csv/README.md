# generate_csv Lambda

This Lambda scans the `tradebot_signals_table` DynamoDB table, applies an optional filter, writes a CSV to S3 under `csv_exports/`, and returns a presigned URL for download.

Environment variables required:
- `S3_BUCKET` - bucket name for CSV uploads
- `DYNAMODB_TABLE` - DynamoDB table name (default: tradebot_signals_table)
- `CSV_PREFIX` - S3 prefix for CSV files (default: csv_exports)
- `CONSISTENT_READ` - true/false

Use the `deploy_generate_csv.ps1` script to package and create/update the Lambda function.
