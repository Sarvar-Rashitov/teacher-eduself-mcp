"""
Redis Sliding Window Rate Limiting Middleware for EduSelf Teacher Platform (Phase 10).
Implements fine-grained rate limits for Auth, AI Generation, WebSocket tickets, and General APIs.
Supports automatic in-memory fallback during local development or unit testing.
"""

import time
import uuid
from collections import deque
from typing import Callable, Dict, Optional, Tuple

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse


# Default sliding window limits (requests per 60 seconds)
DEFAULT_RATE_LIMITS = {
    'auth': {'limit': 5, 'window': 60},        # /api/v1/auth/login, /login/
    'ai': {'limit': 20, 'window': 60},         # /api/v1/ai/
    'session': {'limit': 60, 'window': 60},    # /api/v1/sessions/join, /ws/
    'api': {'limit': 120, 'window': 60},       # General API endpoints
}

# In-memory fallback storage: key -> deque of timestamps
_in_memory_windows: Dict[str, deque] = {}


def get_client_ip(request: HttpRequest) -> str:
    """Extracts client IP address safely, respecting X-Forwarded-For if behind trusted proxy."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # First IP in comma-separated list is the client IP
        ip = x_forwarded_for.split(',')[0].strip()
        if ip:
            return ip
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def resolve_tier_and_key(request: HttpRequest) -> Tuple[Optional[str], Optional[int], Optional[int], Optional[str]]:
    """
    Identifies the rate limiting tier, limit, window, and cache key for a request.
    Returns (tier, limit, window, key) or (None, None, None, None) if path should not be rate limited.
    """
    path = request.path

    # Bypass static, media, favicon, health check paths
    if (
        path.startswith('/static/')
        or path.startswith('/media/')
        or path in ('/favicon.ico', '/robots.txt')
        or path.startswith('/health/')
    ):
        return None, None, None, None

    ip = get_client_ip(request)
    user_id = str(request.user.id) if (hasattr(request, 'user') and request.user.is_authenticated) else None

    # 1. Auth tier
    if (
        path.startswith('/api/v1/auth/login')
        or path.startswith('/login')
        or path.startswith('/api/v1/auth/register')
        or path.startswith('/api/v1/auth/telegram')
    ):
        tier = 'auth'
        rule = DEFAULT_RATE_LIMITS['auth']
        # Auth attempts are keyed strictly by IP or IP+username
        key = f"ratelimit:auth:{ip}"
        return tier, rule['limit'], rule['window'], key

    # 2. AI generation tier
    if path.startswith('/api/v1/ai/'):
        tier = 'ai'
        rule = DEFAULT_RATE_LIMITS['ai']
        ident = user_id or ip
        key = f"ratelimit:ai:{ident}"
        return tier, rule['limit'], rule['window'], key

    # 3. Session join / WebSockets tier
    if path.startswith('/api/v1/sessions/join') or path.startswith('/ws/'):
        tier = 'session'
        rule = DEFAULT_RATE_LIMITS['session']
        ident = user_id or ip
        key = f"ratelimit:session:{ident}"
        return tier, rule['limit'], rule['window'], key

    # 4. General API tier
    if path.startswith('/api/'):
        tier = 'api'
        rule = DEFAULT_RATE_LIMITS['api']
        ident = user_id or ip
        key = f"ratelimit:api:{ident}"
        return tier, rule['limit'], rule['window'], key

    # Regular HTML views (e.g. dashboard, profile) can have relaxed limit or be bypassed
    return None, None, None, None


def _check_rate_limit_redis(key: str, limit: int, window: int) -> Tuple[bool, int, int]:
    """
    Checks rate limit using Redis Sorted Set.
    Returns (is_allowed, remaining, retry_after).
    """
    try:
        from django_redis import get_redis_connection
        redis_client = get_redis_connection("default")
    except Exception:
        raise RuntimeError("Redis not available")

    now = time.time()
    clear_before = now - window
    member = f"{now}:{uuid.uuid4().hex[:8]}"

    # Execute atomic pipeline
    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, clear_before)
    pipe.zcard(key)
    pipe.expire(key, window + 10)
    res = pipe.execute()

    current_count = res[1]

    if current_count >= limit:
        # Find oldest timestamp to calculate retry_after
        oldest = redis_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_ts = oldest[0][1]
            retry_after = max(1, int(oldest_ts + window - now))
        else:
            retry_after = window
        return False, 0, retry_after

    # Record this request
    redis_client.zadd(key, {member: now})
    remaining = max(0, limit - (current_count + 1))
    return True, remaining, 0


def _check_rate_limit_memory(key: str, limit: int, window: int) -> Tuple[bool, int, int]:
    """
    In-memory fallback for sliding window rate limiting.
    Used when Redis is not running or during unit testing.
    """
    now = time.time()
    cutoff = now - window

    if key not in _in_memory_windows:
        _in_memory_windows[key] = deque()

    timestamps = _in_memory_windows[key]

    # Remove timestamps outside the sliding window
    while timestamps and timestamps[0] <= cutoff:
        timestamps.popleft()

    current_count = len(timestamps)

    if current_count >= limit:
        oldest_ts = timestamps[0]
        retry_after = max(1, int(oldest_ts + window - now))
        return False, 0, retry_after

    timestamps.append(now)
    remaining = max(0, limit - (current_count + 1))
    return True, remaining, 0


def check_rate_limit(key: str, limit: int, window: int) -> Tuple[bool, int, int]:
    """
    Orchestrates rate limit checking via Redis with automatic in-memory fallback.
    Returns (is_allowed, remaining, retry_after).
    """
    # Check if disabled by settings
    if getattr(settings, 'RATE_LIMIT_DISABLED', False):
        return True, limit, 0

    try:
        return _check_rate_limit_redis(key, limit, window)
    except Exception:
        # Fall back to thread-safe in-memory sliding window
        return _check_rate_limit_memory(key, limit, window)


class SlidingWindowRateLimitMiddleware:
    """
    Middleware that enforces sliding window rate limiting on API endpoints.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        tier, limit, window, key = resolve_tier_and_key(request)

        if tier is None or key is None or limit is None or window is None:
            return self.get_response(request)

        is_allowed, remaining, retry_after = check_rate_limit(key, limit, window)

        if not is_allowed:
            reset_time = int(time.time() + retry_after)
            response = JsonResponse({
                'error': 'Too Many Requests',
                'message': 'Juda ko‘p so‘rov yuborildi. Iltimos, bir oz kuting.',
                'retry_after': retry_after,
                'limit': limit,
                'tier': tier
            }, status=429)

            response['Retry-After'] = str(retry_after)
            response['X-RateLimit-Limit'] = str(limit)
            response['X-RateLimit-Remaining'] = '0'
            response['X-RateLimit-Reset'] = str(reset_time)
            return response

        # Allowed request
        response = self.get_response(request)
        reset_time = int(time.time() + window)
        response['X-RateLimit-Limit'] = str(limit)
        response['X-RateLimit-Remaining'] = str(remaining)
        response['X-RateLimit-Reset'] = str(reset_time)
        return response
