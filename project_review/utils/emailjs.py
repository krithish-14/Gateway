import json
import os
import requests
from django.conf import settings

def send_emailjs_email(template_params, service_id=None, template_id=None, public_key=None, origin='http://localhost', timeout=10):
    svc = service_id or os.getenv('EMAILJS_SERVICE_ID', '') or getattr(settings, 'EMAILJS_SERVICE_ID', '')
    tpl = template_id or os.getenv('EMAILJS_TEMPLATE_ID_CONTACT', '') or getattr(settings, 'EMAILJS_TEMPLATE_ID_CONTACT', '') or os.getenv('EMAILJS_TEMPLATE_ID_REG', '') or getattr(settings, 'EMAILJS_TEMPLATE_ID_REG', '')
    pub = public_key or os.getenv('EMAILJS_PUBLIC_KEY', '') or getattr(settings, 'EMAILJS_PUBLIC_KEY', '')
    payload = {
        "service_id": svc,
        "template_id": tpl,
        "user_id": pub,
        "template_params": template_params or {},
    }
    headers = {
        "Content-Type": "application/json",
        "Origin": origin,
    }
    try:
        r = requests.post("https://api.emailjs.com/api/v1.0/email/send", json=payload, headers=headers, timeout=timeout)
        return 1 if 200 <= r.status_code < 300 else 0
    except requests.RequestException:
        return 0

def send_emailjs(service_id, template_id, template_params, public_key):
    return send_emailjs_email(template_params, service_id, template_id, public_key)