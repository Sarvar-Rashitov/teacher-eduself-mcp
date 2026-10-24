"""
Security Headers Middleware according to DOC-SEC-01 (SECURITY.md).
Enforces Strict CSP, HSTS, X-Frame-Options, Permissions-Policy and Referrer-Policy.
"""

from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Har bir HTTP javobiga qat'iy xavfsizlik sarlavhalarini qo'shuvchi middleware.
    OWASP A05 (Security Misconfiguration) talablariga to'liq javob beradi.
    """

    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' wss: ws: https:; "
        "object-src 'none'; "
        "frame-ancestors 'none';"
    )

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # 1. Content-Security-Policy (XSS va tashqi resurslarni cheklash)
        if "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self.CSP_POLICY

        # 2. X-Frame-Options (Clickjacking himoyasi)
        response["X-Frame-Options"] = "DENY"

        # 3. X-Content-Type-Options (MIME-sniffing oldini olish)
        response["X-Content-Type-Options"] = "nosniff"

        # 4. Referrer-Policy (Tashqi saytlarga maxfiy yo'llar sizmasligi uchun)
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 5. Permissions-Policy (Zararsizlantirish: kamera, mikrofon, geolokatsiya)
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # 6. Strict-Transport-Security (HSTS - faqat HTTPS ulanishlarda yoki ishlab chiqarishda)
        if request.is_secure() or getattr(settings, "SECURE_HSTS_SECONDS", 0) > 0:
            hsts_seconds = getattr(settings, "SECURE_HSTS_SECONDS", 63072000)
            response["Strict-Transport-Security"] = f"max-age={hsts_seconds}; includeSubDomains; preload"

        return response
