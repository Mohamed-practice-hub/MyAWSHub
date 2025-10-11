# Lambda Deployment Directory

This directory contains deployment packages for all Lambda functions with their dependencies.

## Structure

```
deployment/
├── main-lambda/           # Main trading bot deployment
│   ├── lambda_function.py
│   ├── requests/          # Dependencies
│   └── lambda_function.zip
├── performance-lambda/    # Performance analyzer deployment
│   ├── performance-analyzer.py
│   └── performance-analyzer.zip
├── sentiment-lambda/      # Sentiment-enhanced bot deployment
│   ├── sentiment-simple-lambda.py
│   ├── requests/          # Dependencies
│   └── sentiment-lambda.zip
└── README.md
```

## Benefits

✅ **Clean Project Structure**: Original `Lambda/` folder stays clean with only source code
✅ **Isolated Dependencies**: All pip packages contained in deployment folders
✅ **Easy Deployment**: Automated scripts handle packaging and deployment
✅ **Version Control**: Dependencies not committed to Git (add to .gitignore)

## Usage

### Automated Deployment
```bash
# Windows
Scripts\deploy-clean.bat

# Manual deployment
cd deployment\main-lambda
aws lambda update-function-code --function-name "swing-automation-data-processor-lambda" --zip-file fileb://lambda_function.zip
```

### Manual Package Creation
```bash
# Install dependencies
cd deployment\main-lambda
pip install --no-user requests -t .

# Create package
powershell -Command "Compress-Archive -Path * -DestinationPath lambda_function.zip -Force"

# Deploy
aws lambda update-function-code --function-name "swing-automation-data-processor-lambda" --zip-file fileb://lambda_function.zip
```

## Dependencies

- **requests**: HTTP library for API calls to Alpaca, Finnhub, NewsAPI
- **boto3**: AWS SDK (included in Lambda runtime)
- **json**: Standard library
- **datetime**: Standard library

## Notes

- Dependencies are automatically installed during deployment
- Zip files are created with all dependencies included
- Original source code in `Lambda/` folder remains unchanged
- This approach keeps the project repository clean and organized