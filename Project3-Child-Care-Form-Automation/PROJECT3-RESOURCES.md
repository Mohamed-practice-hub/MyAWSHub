# Project 3 AWS Resources

## All resources created with `project3` prefix for easy identification:

### CloudFormation Stack
- **Name**: `project3-child-care-stack`
- **Description**: Main stack containing all resources

### Lambda Function
- **Name**: `project3-child-care-process-form`
- **Runtime**: Python 3.9
- **Purpose**: Process form data and send WhatsApp messages

### API Gateway
- **Name**: `project3-child-care-api`
- **Type**: REST API
- **Endpoint**: `/childcare` (POST method)

### SNS Topic
- **Name**: `project3-child-care-whatsapp`
- **Purpose**: Send SMS/WhatsApp messages
- **Subscription**: Mohamed's phone (+14166484282)

### IAM Role
- **Name**: `project3-child-care-lambda-role`
- **Purpose**: Lambda execution role with SNS permissions

## Quick Commands

### Deploy Project
```bash
bash SH/deploy-project3.sh
```

### Check Resources
```bash
# List all project3 resources
aws resourcegroupstaggingapi get-resources --tag-filters Key=aws:cloudformation:stack-name,Values=project3-child-care-stack

# Check Lambda function
aws lambda get-function --function-name project3-childcare-automation-form-processor

# Check API Gateway
aws apigateway get-rest-apis --query 'items[?name==`project3-childcare-automation-automation-api`]'

# Check SNS topic
aws sns list-topics --query 'Topics[?contains(TopicArn, `project3-childcare`)]'
```

### Test System
```bash
# Test Lambda directly
aws lambda invoke --function-name project3-childcare-automation-form-processor --payload file://JSON/test-events.json response.json

# Check logs
aws logs filter-log-events --log-group-name "/aws/lambda/project3-childcare-automation-form-processor"
```

### Cleanup
```bash
bash SH/cleanup-project3.sh
```

## Resource Naming Convention
All resources follow the pattern: `project3-child-care-{resource-type}`

This makes it easy to:
- ✅ Identify Project 3 resources
- ✅ Manage permissions
- ✅ Monitor costs
- ✅ Clean up when needed