aws cloudformation create-stack \
  --stack-name serverless-contact-form \
  --template-body file://contact-form-infrastructure.yaml \
  --parameters ParameterKey=AdminEmail,ParameterValue=your-admin@example.com \
               ParameterKey=SenderEmail,ParameterValue=your-verified@example.com \
  --capabilities CAPABILITY_NAMED_IAM
