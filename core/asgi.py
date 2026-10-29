"""
ASGI config for EduSelf Teacher platform.

It exposes the ASGI callable as a module-level variable named ``application``.
Supports both HTTP and WebSockets via Daphne and Django Channels.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack

if os.getenv("RENDER"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.production")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.local")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# WebSocket routes will be registered via core.routing in Phase 03
try:
    from core.routing import websocket_urlpatterns
except ImportError:
    websocket_urlpatterns = []

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)
