import urllib.request
import urllib.parse

def verify_recaptcha(token, secret_key):
    """Verify reCAPTCHA token with Google"""
    try:
        data = urllib.parse.urlencode({
            'secret': secret_key,
            'response': token
        }).encode()
        
        req = urllib.request.Request(
            'https://www.google.com/recaptcha/api/siteverify',
            data=data,
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result.get('success', False)
    except:
        return False

# Add this to your lambda_handler function after parsing the body:
RECAPTCHA_SECRET = "YOUR_SECRET_KEY"  # Store this in environment variables
recaptcha_token = body.get('recaptchaToken', '')

if not verify_recaptcha(recaptcha_token, RECAPTCHA_SECRET):
    return {
        'statusCode': 400,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        },
        'body': json.dumps({
            'error': 'reCAPTCHA verification failed'
        })
    }
