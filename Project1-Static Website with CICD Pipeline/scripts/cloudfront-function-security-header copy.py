function handler(event) {
    var response = event.response;
    var headers = response.headers;
    
    // Security Headers
    headers['strict-transport-security'] = { value: 'max-age=31536000; includeSubDomains; preload' };
    headers['content-security-policy'] = { 
        value: "default-src 'self'; script-src 'self' 'unsafe-inline' https://apis.google.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self' https://*.execute-api.us-east-1.amazonaws.com;" 
    };
    headers['x-content-type-options'] = { value: 'nosniff' };
    headers['x-frame-options'] = { value: 'DENY' };
    headers['x-xss-protection'] = { value: '1; mode=block' };
    headers['referrer-policy'] = { value: 'strict-origin-when-cross-origin' };
    headers['permissions-policy'] = { 
        value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()' 
    };
    
    // Performance Headers
    headers['cache-control'] = { value: 'public, max-age=31536000' };
    
    return response;
}