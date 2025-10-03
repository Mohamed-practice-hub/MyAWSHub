# Project1: AWS Static Website CI/CD Workflow

## Architecture Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitHub Repo   │───▶│   CodePipeline   │───▶│   S3 Bucket     │
│ (Source Code)   │    │  (CI/CD Engine)  │    │ (Static Hosting)│
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ Lambda Function  │    │   CloudFront    │
                       │(Cache Invalidate)│    │ (Global CDN)    │
                       └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │   End Users     │
                                               │ (Global Access) │
                                               └─────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Contact Form    │───▶│  API Gateway     │───▶│ Lambda Function │
│   (Frontend)    │    │   (REST API)     │    │ (Form Handler)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │      SES        │
                                               │ (Email Service) │
                                               └─────────────────┘
```

## Workflow Steps

### 1. Development Workflow
```
Developer → Git Push → GitHub → CodePipeline Trigger
```

### 2. CI/CD Pipeline Flow
```
Source Stage:
├── GitHub Repository (Mohamed-practice-hub/aws-portfolio-web-app)
├── Branch: main
└── Trigger: Automatic on push

Deploy Stage:
├── Target: S3 Bucket (project1-aws-portfolio-website)
├── Action: Extract files and deploy
└── Result: Website files updated

Invalidation Stage:
├── Lambda Function: cloudfront-invalidation
├── Action: Clear CloudFront cache
└── Result: Immediate content refresh
```

### 3. Contact Form Flow (with Issue Resolution)
```
User Submits Form → API Gateway → Lambda Function → SES → Email Sent
                        ↓              ↓
                 Proxy Integration   Validation & Processing
                 (Fixed UNKNOWN      ├── Name validation
                  method issue)      ├── Email format check
                                     ├── CORS handling
                                     ├── Case-sensitive email
                                     └── Comprehensive error logging
```

### 4. Content Delivery Flow
```
User Request → CloudFront Edge Location → Origin (S3) → Response
                    ↓
            Security Headers Added
            ├── HSTS
            ├── CSP
            ├── X-Frame-Options
            └── XSS Protection
```

## Key Components

### Infrastructure
- **S3 Bucket**: `project1-aws-portfolio-website`
- **CloudFront Distribution**: `E2WPPNQQHU3K9B`
- **Domain**: `https://d1h5qajn6cztrt.cloudfront.net`

### CI/CD Pipeline
- **Pipeline**: `project1-portfolio-deployment-pipeline`
- **Connection**: GitHub CodeConnections
- **Trigger**: Automatic on main branch push

### Serverless Backend
- **Contact Form API**: `https://lgmh26izte.execute-api.us-east-1.amazonaws.com/project1-prod/contact`
- **Lambda Functions**:
  - `lambda-form.py` (Contact form processing)
  - `cloudfront-invalidation.py` (Cache management)

### Security & Monitoring
- **IAM Roles**: Least privilege access
- **Security Headers**: CloudFront Functions
- **Error Handling**: Comprehensive logging
- **CORS**: Properly configured

## Technical Issues Faced & Solutions

### 1. CodePipeline Permission Issues
**Problem**: Pipeline failed with "insufficient permissions" error
**Root Cause**: AWS service transition from `codestar-connections` to `codeconnections`
**Solution**: Added both service prefixes to IAM policy:
```json
{
    "Effect": "Allow",
    "Action": [
        "codeconnections:UseConnection",
        "codeconnections:GetConnection", 
        "codestar-connections:UseConnection",
        "codestar-connections:GetConnection"
    ],
    "Resource": [
        "arn:aws:codeconnections:us-east-1:*:connection/*",
        "arn:aws:codestar-connections:us-east-1:*:connection/*"
    ]
}
```

### 2. Lambda "Method UNKNOWN" Error
**Problem**: Contact form Lambda receiving `"httpMethod": "UNKNOWN"` instead of `"POST"`
**Root Cause**: API Gateway missing Lambda Proxy Integration
**Solution**: Enabled Lambda Proxy Integration in API Gateway
- Before: Direct Lambda integration (no HTTP context)
- After: Proxy integration (full HTTP request/response)

### 3. CodePipeline Lambda Invocation Error
**Problem**: "The provided role does not have lambda:InvokeFunction permission"
**Root Cause**: CodePipeline service role missing Lambda invoke permissions
**Solution**: Added Lambda invoke permission to CodePipeline role:
```json
{
    "Effect": "Allow",
    "Action": "lambda:InvokeFunction",
    "Resource": "arn:aws:lambda:us-east-1:*:function:cloudfront-invalidation"
}
```

### 4. AWS Service Propagation Delays
**Problem**: Intermittent failures after configuration changes
**Root Cause**: AWS services have 5-15 minute propagation delays
**Solution**: 
- Always redeploy API Gateway after changes
- Wait 10-15 minutes before testing
- Use systematic testing approach (API Gateway TEST → Direct API → Full website)

### 5. SES Email Delivery Issues
**Problem**: Emails not received from contact form
**Root Cause**: Case-sensitive email verification in SES
**Solution**: Ensured exact email case match between SES verified identity and Lambda code

## Technical Achievements

1. **Automated Deployment**: Zero-downtime deployments with cache invalidation
2. **Global Performance**: CloudFront CDN with security headers
3. **Serverless Architecture**: Cost-effective scaling with comprehensive error handling
4. **Security Best Practices**: A+ security rating with CloudFront Functions
5. **Production Debugging**: Real-world AWS service integration challenges resolved
6. **Cost Optimization**: <$2/month operational cost