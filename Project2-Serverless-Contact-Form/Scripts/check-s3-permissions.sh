#!/bin/bash

BUCKET_NAME="projects-mohamed-aws-portfolio"

echo "Checking S3 bucket permissions..."

# Check public access block
echo "=== Public Access Block Status ==="
aws s3api get-public-access-block --bucket $BUCKET_NAME

# Check bucket policy
echo "=== Bucket Policy ==="
aws s3api get-bucket-policy --bucket $BUCKET_NAME 2>/dev/null || echo "No bucket policy found"

# Test anonymous access using IAM simulator
echo "=== IAM Policy Simulation ==="
aws iam simulate-principal-policy \
    --policy-source-arn "arn:aws:iam::*:root" \
    --action-names "s3:GetObject" \
    --resource-arns "arn:aws:s3:::$BUCKET_NAME/*"