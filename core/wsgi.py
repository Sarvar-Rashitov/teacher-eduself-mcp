"""
WSGI config for EduSelf Teacher platform.

It exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
from django.core.wsgi import get_wsgi_application

if os.getenv("RENDER"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.production")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.local")

application = get_wsgi_application()
