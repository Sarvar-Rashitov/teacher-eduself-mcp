# core/middleware/audit_log.py
"""
Security Audit Log & PII Scrubber Middleware.
SECURITY.md §6 & §7 (Zero-PII & Append-Only Audit Trail) asosida.
"""
import time
import json
import logging
from django.utils import timezone
from django.core.cache import cache

audit_logger = logging.getLogger('security.audit')

SENSITIVE_KEYS = {
    'password', 'pass', 'secret', 'token', 'access_token', 'refresh_token',
    'api_key', 'apikey', 'authorization', 'cookie', 'csrfmiddlewaretoken'
}


class SecurityAuditLogMiddleware:
    """
    O'zgaruvchi (mutating) va autentifikatsiya amallarini maxfiy ma'lumotlarsiz
    (Zero-PII) strukturaviy audit jurnali sifatida yozuvchi middleware.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def scrub_data(data: dict) -> dict:
        """Parol, token va API kalitlarni tozalash (Scrubbing)."""
        if not isinstance(data, dict):
            return data

        scrubbed = {}
        for key, value in data.items():
            if str(key).lower() in SENSITIVE_KEYS:
                scrubbed[key] = '[REDACTED]'
            elif isinstance(value, dict):
                scrubbed[key] = SecurityAuditLogMiddleware.scrub_data(value)
            elif isinstance(value, list):
                scrubbed[key] = [
                    SecurityAuditLogMiddleware.scrub_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                scrubbed[key] = value
        return scrubbed

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Faqat holatni o'zgartiruvchi yoki autentifikatsiya amallari bo'yicha audit yozish
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE'] or request.path in ['/login/', '/logout/']:
            actor_id = str(request.user.id) if hasattr(request, 'user') and request.user.is_authenticated else 'anonymous'
            
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR', '127.0.0.1')

            audit_entry = {
                'timestamp': timezone.now().isoformat(),
                'actor_id': actor_id,
                'ip': client_ip,
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration_ms': duration_ms,
            }

            # Log yozish
            audit_logger.info(f"AUDIT_EVENT: {json.dumps(audit_entry)}")

            # Testlar uchun oxirgi audit logini cache'da saqlash
            cache.set("latest_security_audit_event", audit_entry, timeout=60)

        return response
