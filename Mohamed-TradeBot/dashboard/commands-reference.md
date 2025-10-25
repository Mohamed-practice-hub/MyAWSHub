# Dashboard - Commands Reference

This file collects the working PowerShell/AWS CLI commands used to deploy the static dashboard and wiring (S3 website + bucket policy + Cognito + Lambda exporter). Replace placeholders where needed.

## Variables (set before running)
```powershell
$REGION = 'us-east-1'
$ACCOUNT = '<YOUR_AWS_ACCOUNT_ID>'
$BUCKET = 'tradebot-206055866143-dashboard'   # your bucket
$DDB_TABLE = 'tradebot_signals_table'         # your table
$LAMBDA_ROLE_ARN = 'arn:aws:iam::<ACCOUNT>:role/tradebot-lambda-role' # update
```

---

## 1) Create S3 bucket (use script)
If you used `create-s3-bucket.ps1` to create a readable name, run:
```powershell
cd .\dashboard
.\create-s3-bucket.ps1
# the script prints the created bucket name and saves it to %TEMP%\created_bucket_name.txt
```

Or create manually:
```powershell
aws s3api create-bucket --bucket $BUCKET --region $REGION --create-bucket-configuration LocationConstraint=$REGION
aws s3 website s3://$BUCKET/ --index-document index.html --error-document index.html
```

---

## 2) Upload only website assets (keep S3 minimal)
```powershell
# copy only the site files
aws s3 cp .\index.html s3://$BUCKET/index.html --region $REGION
aws s3 cp .\styles.css s3://$BUCKET/styles.css --region $REGION
aws s3 cp .\data.json s3://$BUCKET/data.json --region $REGION
aws s3 cp .\config.json s3://$BUCKET/config.json --region $REGION  # optional
```

---

## 3) Make bucket objects publicly readable (if not using CloudFront)
Create a JSON policy file `s3_policy.json` (or use the temp approach below).

Policy content (save in file):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::$BUCKET/*"]
    }
  ]
}
```

Apply it (use a short path to avoid quoting issues):
```powershell
Copy-Item .\s3_policy.json $env:TEMP\s3_policy.json -Force
aws s3api put-bucket-policy --bucket $BUCKET --policy file://$env:TEMP\s3_policy.json --region $REGION
```

If your account blocks public policies, consider CloudFront OAI instead (see below).

---

## 4) Create Cognito Identity Pool and role (for direct-DynamoDB access if needed)
This is optional if you plan to only read `data.json` from S3.

Create identity pool:
```powershell
$IDENTITY_POOL_NAME = 'tradebot-dashboard-identity-pool'
$pool = aws cognito-identity create-identity-pool --identity-pool-name $IDENTITY_POOL_NAME --allow-unauthenticated-identities --region $REGION --output json
$IDENTITY_POOL_ID = ($pool | ConvertFrom-Json).IdentityPoolId
```

Create a trust policy file (trust-policy.json) that uses the identity pool id and unauthenticated access. Then create the role and attach a minimal DynamoDB read-only policy.

Example minimal policy (replace ACCOUNT/table):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:Query","dynamodb:GetItem","dynamodb:Scan"],
      "Resource": "arn:aws:dynamodb:us-east-1:YOUR_ACCOUNT_ID:table/tradebot_signals_table"
    }
  ]
}
```

Attach and set roles on identity pool using `aws cognito-identity set-identity-pool-roles`.

---

## 5) Enable DynamoDB Streams (if using exporter Lambda)
Enable streams for the table:
```powershell
aws dynamodb update-table --table-name $DDB_TABLE --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES --region $REGION
```
Confirm Stream ARN:
```powershell
aws dynamodb describe-table --table-name $DDB_TABLE --region $REGION --query 'Table.LatestStreamArn' --output text
```

---

## 6) Deploy DynamoDB Stream -> S3 exporter Lambda
You can run the Windows deploy script in dashboard:
```powershell
cd .\dashboard
# edit deploy-dynamo-exporter.ps1 to set $ROLE_ARN, $DDB_TABLE, $S3_BUCKET
.\deploy-dynamo-exporter.ps1
```

Or the bash equivalent for Linux/Mac:
```bash
cd dashboard
chmod +x deploy-dynamo-exporter.sh
./deploy-dynamo-exporter.sh
```

This sets up an event source mapping so updates to the DynamoDB table cause the Lambda to write a new `data.json` snapshot to S3.

---

## 7) Quick verification
Download and inspect the S3 file locally:
```powershell
aws s3 cp s3://$BUCKET/data.json .\data.json --region $REGION
Get-Content .\data.json -TotalCount 50
```
Check your website:
```powershell
Start-Process 'http://'$BUCKET'.s3-website-'$REGION'.amazonaws.com'
```

---

## 8) Use CloudFront with OAI (recommended for production)
If you prefer to keep the bucket private and serve via CloudFront:
- Create an Origin Access Identity (OAI) and note the S3 canonical user ID
- Add a bucket policy granting that canonical user `s3:GetObject` on the bucket
- Create/Configure a CloudFront distribution for the bucket origin and set default root object to index.html

I can generate a CLI-backed CloudFront distribution JSON if you want to automate this.

---

## Notes
- Keep this file updated with any changes you test. Store sensitive values (tokens or secrets) securely — never commit them.
- For small tables, full-table export on stream events is fine. For bigger tables, implement incremental updates in the exporter Lambda.

