# app.py - Flask Backend for Exodus 2026 Contact Form (Corrected)

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail, Message
from markupsafe import escape
import re
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

# --------------------------------------------------
# App initialization
# --------------------------------------------------
app = Flask(__name__)
CORS(app)

# --------------------------------------------------
# Basic security limits
# --------------------------------------------------
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB request limit

# --------------------------------------------------
# Mail configuration
# --------------------------------------------------
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=EMAIL_USER,
    MAIL_PASSWORD=EMAIL_PASSWORD,
    MAIL_DEFAULT_SENDER=f"Exodus 2026 <{EMAIL_USER}>",
    ADMIN_EMAIL=os.getenv('ADMIN_EMAIL', EMAIL_USER)
)

# --------------------------------------------------
# Logging
# --------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------------------------------
# Extensions
# --------------------------------------------------
mail = Mail(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # Use Redis in production
)

# --------------------------------------------------
# Validation logic
# --------------------------------------------------
def validate_contact_form(data):
    errors = []

    # Name
    name = data.get('name', '').strip()
    if len(name) < 2:
        errors.append("Name must be at least 2 characters long")
    elif len(name) > 100:
        errors.append("Name must be less than 100 characters")

    # Email
    email = data.get('email', '').strip()
    email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    if not re.match(email_regex, email):
        errors.append("Please provide a valid email address")

    # Phone (optional)
    phone = data.get('phone', '').strip()
    if phone:
        phone_clean = re.sub(r'[^\d]', '', phone)
        # Basic length check for international numbers
        if len(phone_clean) < 10 or len(phone_clean) > 15:
            errors.append("Please provide a valid phone number")

    # Message
    message = data.get('message', '').strip()
    if len(message) < 10:
        errors.append("Message must be at least 10 characters long")
    elif len(message) > 1000:
        errors.append("Message must be less than 1000 characters")

    return errors

# --------------------------------------------------
# Routes
# --------------------------------------------------

@app.route('/api/contact', methods=['POST'])
@limiter.limit("5 per 15 minutes")
def contact():
    try:
        data = request.get_json(silent=True)
        print("DEBUG: RECEIVED DATA:", data)
        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "errors": ["Invalid or missing JSON data"]
            }), 400

        # Validate
        errors = validate_contact_form(data)
        if errors:
            return jsonify({"success": False, "errors": errors}), 400

        # Sanitize inputs
        # CRITICAL FIX: Ensure phone is captured here!
        name = escape(data['name'].strip()[:100])
        email = escape(data['email'].strip().lower())
        phone = escape(data.get('phone', '').strip()[:20]) # <--- This line ensures phone is captured
        message_text = escape(data['message'].strip()[:1000])
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # --------------------------------------------------
        # Admin email
        # --------------------------------------------------
        admin_msg = Message(
            subject="New Contact Form Submission - Exodus 2026",
            recipients=[app.config['ADMIN_EMAIL']],
            body=f"""
New contact form submission:

Name: {name}
Email: {email}
Phone: {phone if phone else 'Not provided'}
Date: {timestamp}

Message:
{message_text}
            """,
            html=f"""
<html>
<body style="font-family: Arial, sans-serif; color:#333;">
    <div style="max-width:600px;margin:auto;padding:20px;">
        <h2 style="color:#dc143c;">New Contact Form Submission</h2>
        <p><strong>Name:</strong> {name}</p>
        <p><strong>Email:</strong> {email}</p>
        <p><strong>Phone:</strong> {phone if phone else 'Not provided'}</p>
        <p><strong>Date:</strong> {timestamp}</p>
        <hr>
        <p><strong>Message:</strong></p>
        <p style="white-space:pre-wrap;background:#f5f5f5;padding:15px;">
            {message_text}
        </p>
    </div>
</body>
</html>
            """
        )

        # --------------------------------------------------
        # User confirmation email
        # --------------------------------------------------
        user_msg = Message(
            subject="Thank you for contacting Exodus 2026",
            recipients=[email],
            body=f"""
Hello {name},

Thank you for contacting Exodus 2026.
We have received your message and will respond shortly.

Your message:
{message_text}

Regards,
Exodus 2026 Team
            """,
            html=f"""
<html>
<body style="font-family: Arial, sans-serif; color:#333;">
    <div style="max-width:600px;margin:auto;padding:20px;">
        <h2 style="color:#dc143c;">Thank You for Contacting Us</h2>
        <p>Hello <strong>{name}</strong>,</p>
        <p>We have received your message and will get back to you soon.</p>
        <div style="background:#f5f5f5;padding:15px;">
            <strong>Your message:</strong>
            <p style="white-space:pre-wrap;">{message_text}</p>
        </div>
        <p>— Exodus 2026 Team</p>
    </div>
</body>
</html>
            """
        )

        try:
            mail.send(admin_msg)
            mail.send(user_msg)
        except Exception as mail_error:
            logger.error(f"Mail sending failed: {mail_error}")
            return jsonify({
                "success": False,
                "message": "Email service temporarily unavailable."
            }), 503

        return jsonify({
            "success": True,
            "message": "Thank you! Your message has been sent successfully."
        }), 200

    except Exception as e:
        logger.exception("Unhandled server error")
        return jsonify({
            "success": False,
            "message": "Internal server error."
        }), 500

# --------------------------------------------------
# Health check
# --------------------------------------------------
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }), 200

# --------------------------------------------------
# Entry point
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)