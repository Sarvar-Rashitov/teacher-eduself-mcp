# ============================================================
# EduSelf Teacher — core/asgi.py
# Daphne ASGI serveri — HTTP + WebSocket birlashgan routing
# TECH_STACK.md §3.2 asosida: ProtocolTypeRouter (Channels 4.x API)
# ============================================================
import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.local')

# Django'ni ishga tushirishdan oldin sozlamalarni yuklaymiz
django.setup()

# Routing faylini django.setup() DAN KEYIN import qilamiz
import core.routing  # noqa: E402

application = ProtocolTypeRouter({
    # Oddiy HTTP so'rovlari Django MVT ga yo'naltiriladi
    'http': get_asgi_application(),

    # WebSocket so'rovlari Channels Consumers ga yo'naltiriladi
    # AuthMiddlewareStack: Django sessiyasi orqali foydalanuvchini aniqlaydi
    'websocket': AuthMiddlewareStack(
        URLRouter(core.routing.websocket_urlpatterns)
    ),
})
