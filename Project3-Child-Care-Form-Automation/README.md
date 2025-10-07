# Project 3: Child Care Form Automation with WhatsApp Messaging

## Overview
Automated system to capture daily child care reports and send formatted WhatsApp messages to parents.

## Architecture
- **Frontend**: HTML form for daily report submission
- **Backend**: Lambda function processes form data
- **Messaging**: SNS sends WhatsApp messages to parents
- **API**: API Gateway handles form submissions

## Features
- ✅ Daily child care report form
- ✅ Automatic WhatsApp message generation
- ✅ Formatted messages with emojis
- ✅ CORS-enabled API
- ✅ Error handling and validation
- ✅ No data storage - just message sending

## Deployment Steps

### 1. Deploy Infrastructure
```bash
# Run the deployment script
bash SH/deploy-project3.sh

# Or manually:
aws cloudformation create-stack \
  --stack-name project3-child-care-stack \
  --template-body file://YAML/child-care-infrastructure.yaml \
  --parameters ParameterKey=ParentPhoneNumber,ParameterValue=+14166484282 \
  --capabilities CAPABILITY_NAMED_IAM
```

### 2. Update Lambda Code
Replace the basic Lambda code with the enhanced version from `Lambda/ProcessChildCareForm.py`

### 3. Update HTML Form
Update the API endpoint in `HTML/child-care-form.html` with your API Gateway URL

### 4. Test the System
Use the test events in `JSON/test-events.json` to test the Lambda function

## Message Format
WhatsApp messages include:
- 🍼 Feeding information
- 😴 Sleep/nap times
- 🍽️ Meal details
- 🚼 Diaper changes
- 📝 Daily notes and milestones
- 💕 Friendly closing

## Configuration
- **Phone Number**: Update in CloudFormation parameters
- **Message Format**: Customize in Lambda function
- **Form Fields**: Modify HTML form as needed

## Files Structure
```
Project3-Child-Care-Form-Automation/
├── HTML/
│   └── child-care-form.html
├── Lambda/
│   └── ProcessChildCareForm.py
├── YAML/
│   └── child-care-infrastructure.yaml
├── JSON/
│   └── test-events.json
├── SH/
│   ├── deploy-project3.sh
│   └── cleanup-project3.sh
├── README.md
└── PROJECT3-RESOURCES.md
```

## Usage
1. Fill out the daily report form
2. Submit the form
3. Parent receives formatted WhatsApp message immediately

## Cost Optimization
- Lambda: Only charged when form is submitted
- SNS: Minimal cost for SMS messages
- API Gateway: Pay per API call
- No storage costs - very economical!

## Security
- CORS enabled for web form
- IAM roles with minimal permissions
- Input validation and error handling