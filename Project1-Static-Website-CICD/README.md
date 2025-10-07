# Project 1: Static Website with CI/CD Pipeline

## 📁 Project Structure

```
Project1-Static-Website-CICD/
├── Forms/
│   ├── index.html                # Main website page
│   ├── contact.html              # Contact form page
│   └── error.html                # Error page
├── Lambda/
│   ├── cloudfront-invalidation.py           # CloudFront cache invalidation
│   ├── lambda-form.py                       # Contact form processor
│   ├── cloudfront-function-security-header.py  # Security headers
│   └── cloudfront-function-security-header-TEST.py  # Test version
├── Security/
│   ├── codepipeline-role-perm.json          # CodePipeline IAM permissions
│   ├── ses-lambda-permission.json           # SES Lambda permissions
│   ├── cloundfront-invalidation-lambda-permission.json  # CloudFront permissions
│   ├── codepipeline-perm-to-invoke-lambda.json  # Pipeline Lambda permissions
│   └── testemail.json                       # Test email configuration
├── Scripts/
│   └── styles.css                           # Website styling
├── buildspec.yml                            # CodeBuild specification
└── README.md                                # This file
```

## 🚀 Features

- **Static Website Hosting**: S3 + CloudFront CDN
- **CI/CD Pipeline**: CodePipeline + CodeBuild + GitHub integration
- **Contact Form**: Lambda + SES email processing
- **Security Headers**: CloudFront Functions for security
- **Cache Invalidation**: Automated CloudFront cache clearing
- **Custom Domain**: Route 53 DNS configuration
- **SSL Certificate**: AWS Certificate Manager integration

## 💰 Cost Estimate

- **S3**: $0.023 per GB/month (likely $0-1/month)
- **CloudFront**: $0.085 per GB + $0.0075 per 10,000 requests
- **Lambda**: Free tier (1M requests/month)
- **CodePipeline**: $1/month per active pipeline
- **CodeBuild**: $0.005 per build minute
- **Route 53**: $0.50 per hosted zone/month
- **Total**: ~$2-10/month depending on traffic

## 🛠️ Architecture

1. **Source**: GitHub repository
2. **Build**: CodeBuild compiles and optimizes
3. **Deploy**: Automated S3 deployment
4. **CDN**: CloudFront global distribution
5. **DNS**: Route 53 custom domain
6. **SSL**: Certificate Manager HTTPS
7. **Monitoring**: CloudWatch logs and metrics

## 📧 Components

- **Static Website**: HTML/CSS/JS hosted on S3
- **CI/CD Pipeline**: Automated deployment from GitHub
- **Contact Form**: Serverless form processing
- **CDN**: Global content delivery
- **Security**: Headers and SSL encryption
- **Monitoring**: Performance and error tracking