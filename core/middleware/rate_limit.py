# core/middleware/rate_limit.py
"""
Redis Sliding Window Rate Limiter Middleware.
SECURITY.md §3, §9 va OWASP Top 10 A04/A07 asosida.
"""
import sys
import time
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse


class SlidingWindowRateLimitMiddleware:
    """
    So'rovlar sonini Sliding Window algoritmi orqali tekshiruvchi tezlik cheklovchisi.
    Kategoriya bo'yicha cheklovlar:
    - Auth/Login: 5 ta / daqiqa
    - AI Tasks: 20 ta / daqiqa
    - WebSocket / Real-time: 60 ta / daqiqa
    - Standart API va Sahifalar: 100 ta / daqiqa
    """
    WINDOW_SECONDS = 60

    LIMITS = {
        'auth': 5,
        'ai': 20,
        'ws': 60,
        'default': 100,
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def get_client_identifier(self, request) -> str:
        """Mijozni identifikatsiya qilish: User ID yoki IP manzil."""
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"usr_{request.user.id}"

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return f"ip_{ip}"

    def categorize_request(self, path: str) -> str:
        """So'rov manziliga qarab cheklov toifasini aniqlash."""
        if path.startswith('/api/auth/') or path == '/login/':
            return 'auth'
        if path.startswith('/api/ai/'):
            return 'ai'
        if path.startswith('/ws/'):
            return 'ws'
        return 'default'

    def is_rate_limited(self, identifier: str, category: str) -> tuple[bool, int]:
        """
        Sliding Window hisoblagichi.
        (is_limited, retry_after_seconds) qaytaradi.
        """
        max_allowed = self.LIMITS.get(category, self.LIMITS['default'])
        key = f"rl_{category}_{identifier}"
        now = time.time()
        window_start = now - self.WINDOW_SECONDS

        timestamps = cache.get(key, [])
        # Eski (oynadan tashqari) timestamps larni olib tashlash
        valid_timestamps = [ts for ts in timestamps if ts > window_start]

        if len(valid_timestamps) >= max_allowed:
            oldest_ts = valid_timestamps[0]
            retry_after = max(1, int(oldest_ts + self.WINDOW_SECONDS - now))
            return True, retry_after

        valid_timestamps.append(now)
        cache.set(key, valid_timestamps, timeout=self.WINDOW_SECONDS + 5)
        return False, 0

    def __call__(self, request):
        path = request.path

        # Statik fayllar va admin resurslarini tekshiruvdan o'tkazmaslik
        if path.startswith('/static/') or path.startswith('/admin/'):
            return self.get_response(request)

        # Test muhitida (pytest) faqat maxsus HTTP_X_TEST_ENABLE_RATE_LIMIT sarlavhasi berilganda tekshiriladi
        if 'pytest' in sys.modules or getattr(settings, 'TESTING', False):
            if not request.META.get('HTTP_X_TEST_ENABLE_RATE_LIMIT'):
                return self.get_response(request)

        category = self.categorize_request(path)
        identifier = self.get_client_identifier(request)

        is_limited, retry_after = self.is_rate_limited(identifier, category)

        if is_limited:
            if request.headers.get('Accept') == 'application/json' or path.startswith('/api/'):
                response = JsonResponse({
                    'success': False,
                    'error': {
                        'code': 'RATE_LIMIT_EXCEEDED',
                        'message': f"Tezlik chegarasi oshib ketdi ({self.LIMITS[category]} ta/{self.WINDOW_SECONDS}s). Iltimos bir ozdan so'ng qayta urinib ko'ring.",
                        'retry_after': retry_after
                    }
                }, status=429)
            else:
                response = HttpResponse(
                    f"<h1>429 Too Many Requests</h1><p>Iltimos, {retry_after} soniyadan so'ng qayta urinib ko'ring.</p>",
                    status=429,
                    content_type="text/html"
                )
            response['Retry-After'] = str(retry_after)
            return response

        return self.get_response(request)
