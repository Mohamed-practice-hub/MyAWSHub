#!/bin/bash

BUCKET_NAME="projects-mohamed-aws-portfolio"

echo "Configuring S3 bucket for static website hosting..."

# Remove public access block
aws s3api put-public-access-block \
    --bucket $BUCKET_NAME \
    --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Configure website hosting
aws s3 website s3://$BUCKET_NAME --index-document index.html --error-document error.html

# Apply bucket policy
aws s3api put-bucket-policy --bucket $BUCKET_NAME --policy file://fix-s3-permissions.json

echo "S3 bucket configured successfully!"
echo "Website URL: http://$BUCKET_NAME.s3-website-us-east-1.amazonaws.com"