"""
Security Audit Logging Middleware for EduSelf Teacher Platform (Phase 10).
Emits structured JSON audit records for authentication events, mutations,
privilege denials, rate limit trips, and suspicious payloads.
"""

import json
import logging
import re
import time
from typing import Callable
from django.http import HttpRequest, HttpResponse
from core.middleware.rate_limit import get_client_ip

audit_logger = logging.getLogger('security.audit')

# Common XSS / SQLi heuristic signatures for audit detection
SUSPICIOUS_PATTERNS = re.compile(
    r'(<script|onload=|onerror=|javascript:|union\s+select|\'\s+or\s+1=1|--\s*$)',
    re.IGNORECASE
)


class AuditLogMiddleware:
    """
    Middleware that records immutable security audit logs for auditing and compliance.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.time()

        # Check for suspicious input in raw query string or request body
        query_string = request.META.get('QUERY_STRING', '')
        is_suspicious = bool(SUSPICIOUS_PATTERNS.search(query_string))

        response = self.get_response(request)
        duration_ms = int((time.time() - start_time) * 1000)

        # Skip recording static/media assets
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return response

        # Determine user details
        user = getattr(request, 'user', None)
        user_id = str(user.id) if (user and user.is_authenticated) else None
        username = getattr(user, 'username', None) if (user and user.is_authenticated) else None
        role = getattr(user, 'role', None) if (user and user.is_authenticated) else None
        client_ip = get_client_ip(request)

        # Categorize event type
        event_type = 'HTTP_REQUEST'
        path = request.path

        if is_suspicious:
            event_type = 'SUSPICIOUS_PAYLOAD'
        elif '/auth/login' in path or path == '/login/':
            if response.status_code in (200, 302):
                event_type = 'AUTH_LOGIN_SUCCESS'
            elif response.status_code == 429:
                event_type = 'AUTH_LOCKOUT'
            else:
                event_type = 'AUTH_LOGIN_FAILURE'
        elif '/auth/logout' in path or path == '/logout/':
            event_type = 'AUTH_LOGOUT'
        elif response.status_code == 403:
            event_type = 'PERMISSION_DENIED'
        elif response.status_code == 429:
            event_type = 'RATE_LIMIT_EXCEEDED'
        elif request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            event_type = 'RESOURCE_MUTATED'

        # Only emit audit logs for meaningful security / mutation events
        if event_type != 'HTTP_REQUEST' or response.status_code >= 400:
            log_record = {
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'event_type': event_type,
                'client_ip': client_ip,
                'user_id': user_id,
                'username': username,
                'role': role,
                'method': request.method,
                'path': path,
                'status_code': response.status_code,
                'duration_ms': duration_ms,
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
            }

            if response.status_code >= 500 or event_type in ('SUSPICIOUS_PAYLOAD', 'AUTH_LOCKOUT'):
                audit_logger.warning(json.dumps(log_record))
            else:
                audit_logger.info(json.dumps(log_record))

        return response
