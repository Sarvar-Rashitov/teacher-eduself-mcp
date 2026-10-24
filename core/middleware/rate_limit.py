"""
Redis & Cache Sliding Window Rate Limiting Middleware.
According to DOC-SEC-01 (SECURITY.md) and development_plan.md Phase 10.
"""

import time
import logging
from typing import Callable, Dict, Optional, Tuple
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.conf import settings

logger = logging.getLogger("security.rate_limit")


class SlidingWindowRateLimitMiddleware:
    """
    So'rovlar chastotasini suzuvchi darcha (Sliding Window) usuli bilan cheklovchi middleware.
    DoS, Brute-Force va API kvotasi buzilishlariga qarshi qat'iy himoya ta'minlaydi.
    """

    # Format: (path_prefix, max_requests, window_seconds, bucket_name)
    RULE_MAPPINGS = [
        # 1. Autentifikatsiya (Login, Register, Telegram): 5 ta/daqiqa
        ("/auth/login", 5, 60, "auth_login"),
        ("/auth/register", 5, 60, "auth_register"),
        ("/auth/telegram", 10, 60, "auth_telegram"),
        # 2. AI So'rovlari: 20 ta/daqiqa
        ("/api/ai/", 20, 60, "ai_requests"),
        # 3. Sessiyaga ulanish (WebSocket ticket olish): 60 ta/daqiqa
        ("/api/sessions/join", 60, 60, "session_join"),
        # 4. Google Sheets sinxronizatsiyasi: 30 ta/daqiqa
        ("/api/sheets/", 30, 60, "sheets_sync"),
        # 5. Umumiy REST API va MCP: 120 ta/daqiqa
        ("/api/", 120, 60, "general_api"),
        ("/mcp/", 60, 60, "mcp_api"),
    ]

    EXEMPT_PREFIXES = (
        "/static/",
        "/media/",
        "/health/",
        "/favicon.ico",
    )

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    @staticmethod
    def get_client_ip(request: HttpRequest) -> str:
        """Mijozning haqiqiy IP manzilini X-Forwarded-For yoki REMOTE_ADDR dan olish."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # Vergul bilan ajratilgan birinchi IP mijozning asl IPsi bo'ladi
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "127.0.0.1")

    def find_rule(self, path: str) -> Optional[Tuple[str, int, int, str]]:
        """So'rov yo'liga mos keluvchi cheklov qoidasini aniqlash."""
        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return None

        for rule in self.RULE_MAPPINGS:
            prefix, limit, window, bucket = rule
            if path.startswith(prefix):
                return rule

        return None

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Rate limiting global ravishda o'chirib qo'yilgan bo'lsa (masalan testlarda)
        if getattr(settings, "DISABLE_RATE_LIMITING", False):
            return self.get_response(request)

        rule = self.find_rule(request.path)
        if not rule:
            return self.get_response(request)

        _, limit, window, bucket = rule
        client_ip = self.get_client_ip(request)
        now = time.time()
        cache_key = f"rate_limit:{bucket}:{client_ip}"

        # 1. Joriy so'rovlar vaqt belgilarini olish
        timestamps = cache.get(cache_key) or []

        # 2. Suzuvchi darchadan eski vaqt belgilarini chiqarib tashlash
        valid_timestamps = [ts for ts in timestamps if now - ts < window]

        # 3. Limit tekshiruvi
        if len(valid_timestamps) >= limit:
            oldest_ts = valid_timestamps[0]
            retry_after = max(1, int(window - (now - oldest_ts)))

            logger.warning(
                f"Rate limit exceeded for IP {client_ip} on {request.path} "
                f"(bucket: {bucket}, limit: {limit}/{window}s). Retry after: {retry_after}s"
            )

            response = JsonResponse(
                {
                    "error": "Juda ko'p so'rovlar yuborildi (Rate Limit Exceeded). Iltimos, biroz kuting.",
                    "bucket": bucket,
                    "limit": limit,
                    "retry_after": retry_after,
                },
                status=429,
            )
            response["Retry-After"] = str(retry_after)
            return response

        # 4. Yangi so'rov vaqtini qo'shish va saqlash
        valid_timestamps.append(now)
        cache.set(cache_key, valid_timestamps, timeout=window)

        response = self.get_response(request)
        response["X-RateLimit-Limit"] = str(limit)
        response["X-RateLimit-Remaining"] = str(max(0, limit - len(valid_timestamps)))
        return response
