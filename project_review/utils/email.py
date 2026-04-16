import json
import os
import requests
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import connection

EMAILJS_SERVICE_ID = os.getenv('EMAILJS_SERVICE_ID', '') or getattr(settings, 'EMAILJS_SERVICE_ID', '')
EMAILJS_SERVICE_ID_REG = os.getenv('EMAILJS_SERVICE_ID_REG', '') or getattr(settings, 'EMAILJS_SERVICE_ID_REG', '')
EMAILJS_PUBLIC_KEY = os.getenv('EMAILJS_PUBLIC_KEY', '') or getattr(settings, 'EMAILJS_PUBLIC_KEY', '')
EMAILJS_TEMPLATE_ID_RESET = os.getenv('EMAILJS_TEMPLATE_ID_RESET', '') or getattr(settings, 'EMAILJS_TEMPLATE_ID_RESET', '')
EMAILJS_TEMPLATE_ID_REG = os.getenv('EMAILJS_TEMPLATE_ID_REG', '') or getattr(settings, 'EMAILJS_TEMPLATE_ID_REG', '')
EMAILJS_TEMPLATE_ID_CONTACT = os.getenv('EMAILJS_TEMPLATE_ID_CONTACT', '') or getattr(settings, 'EMAILJS_TEMPLATE_ID_CONTACT', '')

logger = logging.getLogger(__name__)

def send_emailjs_email(template_params, service_id=None, template_id=None, public_key=None, origin=None, timeout=10):
    svc = service_id or EMAILJS_SERVICE_ID
    tpl = template_id or EMAILJS_TEMPLATE_ID_RESET or EMAILJS_TEMPLATE_ID_REG or EMAILJS_TEMPLATE_ID_CONTACT
    pub = public_key or EMAILJS_PUBLIC_KEY
    payload = {
        "service_id": svc,
        "template_id": tpl,
        "user_id": pub,
        "template_params": template_params or {},
    }
    headers = {
        "Content-Type": "application/json",
        "Origin": origin or getattr(settings, 'EMAILJS_ORIGIN', 'http://localhost'),
    }
    try:
        logger.info("EmailJS sending: service_id=%s template_id=%s origin=%s keys=%s", svc, tpl, headers.get("Origin"), ",".join(sorted((template_params or {}).keys())))
        r = requests.post("https://api.emailjs.com/api/v1.0/email/send", json=payload, headers=headers, timeout=timeout)
        if 200 <= r.status_code < 300:
            rid = r.headers.get('x-request-id') or r.headers.get('X-Request-ID') or ''
            logger.info("EmailJS send ok: status=%s template_id=%s request_id=%s", r.status_code, tpl, rid)
            return 1
        rid = r.headers.get('x-request-id') or r.headers.get('X-Request-ID') or ''
        logger.error("EmailJS send failed: status=%s template_id=%s request_id=%s body=%s", r.status_code, tpl, rid, (r.text or '').strip())
        return 0
    except requests.RequestException as e:
        logger.exception("EmailJS request error: %s template_id=%s", e, tpl)
        return 0

def send_emailjs(service_id=None, template_id=None, template_params=None, public_key=None):
    return send_emailjs_email(template_params or {}, service_id, template_id, public_key)

def send_registration_email(email, registration_number, company_name, password, service_id=None, template_id=None, public_key=None, origin='http://localhost', timeout=10, portal_url=None):
    params = {
        'email': email,
        'to_email': email,
        'reply_to': email,
        'registration_number': registration_number,
        'reg_num': registration_number,
        'company_name': company_name,
        'password': password,
        'pin': password,
        'portal_password': password,
    }
    if portal_url:
        params['portal_url'] = portal_url
    return send_emailjs_email(params, service_id or EMAILJS_SERVICE_ID_REG or EMAILJS_SERVICE_ID, template_id or EMAILJS_TEMPLATE_ID_REG, public_key or EMAILJS_PUBLIC_KEY, origin=origin, timeout=timeout)

def send_transactional_email(to_email, subject, text_body, html_body=None, reply_to=None):
    from_email = getattr(settings, 'EMAIL_HOST_USER', '') or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    connection = get_connection()
    msg = EmailMultiAlternatives(
        subject,
        text_body,
        from_email,
        [to_email],
        connection=connection,
        reply_to=[reply_to] if reply_to else None,
    )
    if html_body:
        msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=False)

def send_sql_welcome_email(email, username):
    """
    Sends a welcome email using MS SQL Server's Database Mail (sp_send_dbmail).
    """
    subject = "Welcome to Constructor Gateway"
    body = f"Hello {username},\n\nWelcome to the Gateway! We are thrilled to have you here. This is your personalized dashboard for exploring opportunities and tracking your progress.\n\nBest Regards,\nThe Gateway Team"
    
    try:
        with connection.cursor() as cursor:
            # Command to call Database Mail stored procedure
            sql = """
            EXEC msdb.dbo.sp_send_dbmail
                @profile_name = 'ConstructorMailProfile',
                @recipients = %s,
                @body = %s,
                @subject = %s;
            """
            cursor.execute(sql, [email, body, subject])
            logger.info("SQL Mail sent successfully to %s", email)
            return True
    except Exception as e:
        logger.error("Failed to send SQL Mail to %s: %s", email, str(e))
        return False

def send_welcome_email(email, username, request=None):
    """
    Robust welcome email sender that attempts EmailJS first (if configured),
    then falls back to Django's native SMTP/Console mail.
    """
    subject = "Welcome to Constructor Gateway"
    text_content = f"Hello {username},\n\nWelcome to the Gateway! We are thrilled to have you here. This is your personalized dashboard for exploring opportunities and tracking your progress.\n\nBest Regards,\nThe Gateway Team"
    
    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
        <h2 style="color: #f50e06;">Welcome to Constructor Gateway!</h2>
        <p>Hello <strong>{username}</strong>,</p>
        <p>We are thrilled to have you here. This is your personalized dashboard for exploring opportunities and tracking your progress.</p>
        <div style="background: #f9f9f9; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0;">You can now log in to your account to:</p>
            <ul style="margin-top: 10px;">
                <li>Explore company profiles</li>
                <li>Connect with investors</li>
                <li>Track your startup journey</li>
            </ul>
        </div>
        <p>Best Regards,<br><strong>The Gateway Team</strong></p>
    </div>
    """

    # 1. Try EmailJS if configured
    if EMAILJS_SERVICE_ID and EMAILJS_PUBLIC_KEY and EMAILJS_TEMPLATE_ID_REG:
        logger.info("Attempting Welcome Email via EmailJS for %s", email)
        params = {
            'to_email': email,
            'username': username,
            'subject': subject,
            'message': text_content,
        }
        origin = 'http://localhost'
        if request:
            origin = f"{request.scheme}://{request.get_host()}"
        
        sent = send_emailjs_email(params, origin=origin)
        if sent:
            return True

    # 2. Fallback to Django Transactional Email (SMTP or Console)
    logger.info("Falling back to Transactional Email for %s", email)
    try:
        send_transactional_email(email, subject, text_content, html_content)
        return True
    except Exception as e:
        logger.error("Final fallback email failed for %s: %s", email, str(e))
        return False
