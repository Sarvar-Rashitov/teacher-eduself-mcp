# core/middleware/security_headers.py
"""
OWASP Security Headers Middleware.
SECURITY.md §6.1 asosida barcha HTTP javoblarga xavfsizlik sarlavhalarini ilish.
"""

class SecurityHeadersMiddleware:
    """
    OWASP tavsiya etgan qat'iy xavfsizlik sarlavhalarini o'rnatuvchi middleware.
    """
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: https://storage.eduself.uz; "
        "connect-src 'self' wss: ws: https://storage.eduself.uz; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 1. Content-Security-Policy (XSS & Data Injection himoyasi)
        response['Content-Security-Policy'] = self.CSP_POLICY

        # 2. Strict-Transport-Security (HTTPS majburiy)
        response['Strict-Transport-Security'] = "max-age=63072000; includeSubDomains; preload"

        # 3. X-Frame-Options (Clickjacking himoyasi)
        response['X-Frame-Options'] = "DENY"

        # 4. X-Content-Type-Options (MIME-sniffing himoyasi)
        response['X-Content-Type-Options'] = "nosniff"

        # 5. Referrer-Policy
        response['Referrer-Policy'] = "strict-origin-when-cross-origin"

        # 6. Permissions-Policy (Zararsiz brauzer ruxsatlari)
        response['Permissions-Policy'] = "geolocation=(), microphone=(), camera=()"

        # 7. Cross-Origin-Opener-Policy
        response['Cross-Origin-Opener-Policy'] = "same-origin"

        return response
