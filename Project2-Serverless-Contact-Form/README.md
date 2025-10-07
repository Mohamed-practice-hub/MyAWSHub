# Project 2: Serverless Contact Form

## 📁 Project Structure

```
Project2-Serverless-Contact-Form/
├── Forms/
│   ├── contact.html              # Basic contact form
│   ├── contact-Enh-Validation.html  # Enhanced validation form
│   └── admin.html                # Admin dashboard
├── Lambda/
│   ├── ProcessContactForm.py     # Main contact form processor
│   ├── AdminDashboard.py         # Admin dashboard backend
│   ├── reCAPTCHA.py             # reCAPTCHA validation
│   └── test-logging.py          # Testing utilities
├── Security/
│   ├── ses-lambda-policy.json    # SES permissions for Lambda
│   ├── fix-s3-permissions.json   # S3 bucket permissions
│   ├── lambda-test-api-gateway.json  # API Gateway test events
│   ├── lambda-test-direct.json   # Direct Lambda test events
│   ├── lambda-test-events.json   # General test events
│   └── lambda-test-validation-error.json  # Validation error tests
├── Scripts/
│   ├── check-s3-permissions.sh   # S3 permission checker
│   ├── deploy-cf.sh              # CloudFormation deployment
│   ├── fix-s3-access.sh          # S3 access fixer
│   └── reCAPTCHA-validate.js     # Frontend reCAPTCHA validation
├── contact-form-infrastructure.yaml  # CloudFormation template
└── README.md                     # This file
```

## 🚀 Features

- **Serverless Contact Form**: AWS Lambda + API Gateway + SES
- **Admin Dashboard**: View and manage form submissions
- **reCAPTCHA Integration**: Spam protection
- **Enhanced Validation**: Client and server-side validation
- **CloudFormation**: Infrastructure as Code deployment
- **S3 Integration**: Form data storage and retrieval

## 💰 Cost Estimate

- **Lambda**: Free tier (1M requests/month)
- **API Gateway**: Free tier (1M requests/month)
- **SES**: $0.10 per 1,000 emails
- **S3**: $0.023 per GB/month
- **Total**: ~$0-5/month depending on usage

## 🛠️ Deployment

1. **Deploy Infrastructure**:
   ```bash
   ./Scripts/deploy-cf.sh
   ```

2. **Configure SES**:
   - Verify sender email address
   - Move out of SES sandbox if needed

3. **Upload Forms**:
   - Upload HTML forms to S3 bucket
   - Configure API Gateway endpoints

4. **Test System**:
   - Use test events in Security/ folder
   - Verify email delivery and form submission

## 📧 Components

- **Contact Form**: Collects user inquiries
- **Lambda Processor**: Handles form submissions
- **SES Integration**: Sends email notifications
- **Admin Dashboard**: Manages form responses
- **Security**: IAM policies and test configurations