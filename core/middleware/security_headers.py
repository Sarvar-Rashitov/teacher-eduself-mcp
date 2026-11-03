"""
Security Headers Middleware for EduSelf Teacher Platform (Phase 10).
Injects Content-Security-Policy, HSTS, X-Frame-Options, X-Content-Type-Options,
Referrer-Policy, Cross-Origin-Opener-Policy, and Permissions-Policy into all HTTP responses.
"""

from typing import Callable
from django.conf import settings
from django.http import HttpRequest, HttpResponse


DEFAULT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: https: blob:; "
    "connect-src 'self' ws: wss:; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)


class SecurityHeadersMiddleware:
    """
    Middleware that enforces OWASP-compliant security headers on all HTTP responses.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # 1. Content Security Policy (CSP)
        csp = getattr(settings, 'SECURE_CONTENT_SECURITY_POLICY', DEFAULT_CSP)
        if csp and 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = csp

        # 2. Clickjacking Protection (X-Frame-Options)
        if 'X-Frame-Options' not in response:
            response['X-Frame-Options'] = getattr(settings, 'X_FRAME_OPTIONS', 'DENY')

        # 3. MIME Sniffing Protection (X-Content-Type-Options)
        if 'X-Content-Type-Options' not in response:
            response['X-Content-Type-Options'] = 'nosniff'

        # 4. Referrer Policy
        if 'Referrer-Policy' not in response:
            response['Referrer-Policy'] = getattr(
                settings, 'SECURE_REFERRER_POLICY', 'strict-origin-when-cross-origin'
            )

        # 5. Permissions Policy
        if 'Permissions-Policy' not in response:
            response['Permissions-Policy'] = getattr(
                settings,
                'SECURE_PERMISSIONS_POLICY',
                'geolocation=(), microphone=(), camera=(), payment=()'
            )

        # 6. Cross-Origin Opener Policy (COOP)
        if 'Cross-Origin-Opener-Policy' not in response:
            response['Cross-Origin-Opener-Policy'] = getattr(
                settings, 'SECURE_CROSS_ORIGIN_OPENER_POLICY', 'same-origin'
            )

        # 7. HTTP Strict Transport Security (HSTS)
        hsts_seconds = getattr(settings, 'SECURE_HSTS_SECONDS', 0)
        if (request.is_secure() or hsts_seconds > 0) and hsts_seconds > 0:
            hsts_header = f"max-age={hsts_seconds}"
            if getattr(settings, 'SECURE_HSTS_INCLUDE_SUBDOMAINS', False):
                hsts_header += "; includeSubDomains"
            if getattr(settings, 'SECURE_HSTS_PRELOAD', False):
                hsts_header += "; preload"
            response['Strict-Transport-Security'] = hsts_header

        return response
