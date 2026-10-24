"""
Security Audit Log Middleware according to DOC-SEC-01 (SECURITY.md).
Logs sensitive operations, mutations, and authentication events with structured JSON.
"""

import json
import logging
from typing import Callable
from django.utils import timezone
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("security.audit")


class AuditLogMiddleware:
    """
    Muhim amallar (o'chirish, tahrirlash, autentifikatsiya, ruxsatlar) va
    xavfsizlik hodisalarini kuzatib boruvchi audit middleware.
    """

    SENSITIVE_PREFIXES = (
        "/auth/",
        "/api/quizzes/",
        "/api/sessions/",
        "/api/sheets/",
        "/mcp/",
        "/admin/",
    )

    MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE")

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "127.0.0.1")

    def should_audit(self, request: HttpRequest, response: HttpResponse) -> bool:
        """Qaysi so'rovlar audit jurnaliga yozilishi kerakligini aniqlash."""
        path = request.path

        # Faqat belgilangan xavfsiz prefikslarni kuzatish
        is_sensitive_path = any(path.startswith(prefix) for prefix in self.SENSITIVE_PREFIXES)
        if not is_sensitive_path:
            return False

        # O'zgarish kirituvchi amallar yoki xatoliklar (status >= 400) auditga tushadi
        if request.method in self.MUTATING_METHODS or response.status_code >= 400:
            return True

        # Auth so'rovlari har doim audit qilinadi
        if path.startswith("/auth/"):
            return True

        return False

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        try:
            if self.should_audit(request, response):
                user_id = None
                user_role = "anonymous"
                if hasattr(request, "user") and request.user.is_authenticated:
                    user_id = str(getattr(request.user, "id", ""))
                    user_role = getattr(request.user, "role", "authenticated")

                audit_record = {
                    "event": "security_audit",
                    "timestamp": timezone.now().isoformat(),
                    "ip": self.get_client_ip(request),
                    "method": request.method,
                    "path": request.path,
                    "status_code": response.status_code,
                    "user_id": user_id,
                    "user_role": user_role,
                    "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
                }

                if response.status_code >= 400:
                    logger.warning(json.dumps(audit_record))
                else:
                    logger.info(json.dumps(audit_record))
        except Exception as e:
            # Audit log xatoligi hech qachon asosiy so'rovni to'xtatmasligi kerak
            logger.error(f"AuditLogMiddleware recording failed: {e}")

        return response
