# deploy/health/views.py
"""
Health Check & Monitoring Views (Liveness and Readiness Probes).
DEPLOYMENT_ARCHITECTURE.md §9 va SCALABILITY.md §3 asosida.
"""
import time
from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse


def health_live_view(request):
    """
    Liveness Probe: Server jarayoni tirikligini tasdiqlaydi.
    AWS ALB / Docker / ECS / K8s liveness probe uchun 200 OK qaytaradi.
    """
    return JsonResponse({
        'status': 'alive',
        'service': 'eduself-backend',
        'timestamp': time.time(),
    }, status=200)


def health_ready_view(request):
    """
    Readiness Probe: PostgreSQL va Redis kesh ulanishlarini to'liq tekshiradi.
    Barcha qaramliklar tayyor bo'lsa 200 OK, aks holda 503 Service Unavailable qaytaradi.
    """
    components = {}
    is_healthy = True

    # 1. PostgreSQL DB ulanishini tekshirish
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        components['database'] = {'status': 'healthy'}
    except Exception as e:
        components['database'] = {'status': 'unhealthy', 'error': str(e)}
        is_healthy = False

    # 2. Redis Kesh ulanishini tekshirish
    try:
        test_key = "health_probe_test_key"
        cache.set(test_key, "ok", timeout=5)
        val = cache.get(test_key)
        if val == "ok":
            components['cache'] = {'status': 'healthy'}
        else:
            components['cache'] = {'status': 'unhealthy', 'error': 'Cache get mismatch'}
            is_healthy = False
    except Exception as e:
        components['cache'] = {'status': 'unhealthy', 'error': str(e)}
        is_healthy = False

    status_code = 200 if is_healthy else 503
    return JsonResponse({
        'status': 'ready' if is_healthy else 'not_ready',
        'service': 'eduself-backend',
        'components': components,
        'timestamp': time.time()
    }, status=status_code)
