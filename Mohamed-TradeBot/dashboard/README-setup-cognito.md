Setup: Direct read-only DynamoDB access for the static dashboard

Goal
- Allow the static site to read from DynamoDB directly via Cognito Identity Pool.
- Ensure the browser can only read (Scan/Query/Get), no writes.

Steps
1) Create a Cognito Identity Pool
- In the AWS Cognito console, create a new Identity Pool. Enable unauthenticated identities if you want public read.
- Note the Identity Pool ID (e.g., us-east-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).

2) Create an IAM role for unauthenticated identities
- In IAM, create a new role and choose 'Cognito' as the trusted entity, then select 'Cognito Identity Pool' and select your pool.
- Attach the following minimal policy (replace ACCOUNT_ID and region/table name):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Query",
        "dynamodb:GetItem",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:us-east-1:YOUR_ACCOUNT_ID:table/tradebot_table"
    }
  ]
}
```

- Make sure you do NOT grant PutItem or DeleteItem.

3) Configure the Identity Pool to use the new IAM role
- Update the identity pool to use this role for unauthenticated identities (or authenticated as you prefer).

4) Update `dashboard/config.json` and host it with the dashboard
- Copy `config.json.sample` to `config.json` and fill in the values (region, tableName, identityPoolId).
- Upload `dashboard/` to your static site hosting (S3 + CloudFront or similar).

5) Verify
- Open the hosted `index.html` and confirm the table loads.
- You can debug network and Console logs to verify the Cognito credentials are being used.

Notes and security
- Use least-privilege. If you can provide Query parameters (e.g., only read a small subset), prefer Query over Scan.
- If your table grows large, consider a paginated UI or switching to an API for optimized queries.
- For private data, do not enable unauthenticated identities — require sign-in.

Troubleshooting
- If you get AccessDenied errors, inspect the IAM policy attached to the identity role and check the resource ARN.
- Ensure the identityPoolId is correct and the static site is loading `config.json` from the same origin.
