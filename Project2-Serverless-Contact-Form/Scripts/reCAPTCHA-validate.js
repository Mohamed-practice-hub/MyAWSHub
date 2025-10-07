// Validate reCAPTCHA

const recaptchaResponse = grecaptcha.getResponse();

if (!recaptchaResponse) {

    document.getElementById('recaptchaError').textContent = 'Please complete the reCAPTCHA';

    document.getElementById('recaptchaError').style.display = 'block';

    return;

}



// Add to form data

formData.recaptchaToken = recaptchaResponse;

