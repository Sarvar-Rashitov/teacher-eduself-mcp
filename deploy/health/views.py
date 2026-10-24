"""
Health check views for production monitoring, load balancers, and Docker healthcheck probes.
"""

import logging
from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger("core.health")


def liveness_check(request):
    """
    Liveness tekshiruvi:
    Daphne/ASGI dasturiy ta'minot jarayoni tirikligini va so'rovlarga
    javob bera olishini tasdiqlaydi.
    """
    return JsonResponse(
        {
            "status": "live",
            "service": "EduSelf Teacher Core",
        },
        status=200,
    )


def readiness_check(request):
    """
    Readiness tekshiruvi:
    Tizim yangi foydalanuvchi so'rovlarini qabul qilishga tayyormi yoki yo'qligini
    (PostgreSQL va Redis kesh ulanishlarini sinab) tekshiradi.
    Agar biron bir resurs ishlamayotgan bo'lsa, HTTP 503 Service Unavailable qaytaradi.
    """
    checks = {
        "database": False,
        "cache": False,
    }

    # 1. Ma'lumotlar bazasini tekshirish (PostgreSQL SELECT 1)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row and row[0] == 1:
                checks["database"] = True
    except Exception as e:
        logger.error(f"Readiness DB probe failed: {e}")
        checks["database"] = False

    # 2. Redis kesh ulanishini tekshirish
    try:
        probe_key = "__health_probe__"
        cache.set(probe_key, "ok", timeout=10)
        value = cache.get(probe_key)
        if value == "ok":
            checks["cache"] = True
    except Exception as e:
        logger.error(f"Readiness Cache probe failed: {e}")
        checks["cache"] = False

    is_ready = checks["database"] and checks["cache"]
    status_code = 200 if is_ready else 503

    return JsonResponse(
        {
            "status": "ready" if is_ready else "unhealthy",
            "checks": {
                "database": "connected" if checks["database"] else "disconnected",
                "cache": "connected" if checks["cache"] else "disconnected",
            },
        },
        status=status_code,
    )
