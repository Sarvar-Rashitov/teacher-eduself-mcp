# ============================================================
# EduSelf Teacher — core/settings/local.py
# Mahalliy ishlab chiqish sozlamalari
# ============================================================
import os
from .base import *

# python-dotenv .env faylni yuklaydi
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEBUG = True

ALLOWED_HOSTS = ['*']

# ============================================================
# SQLite Fallback — Docker ishlatmasdan tezkor dev
# USE_SQLITE=1 qilib ishga tushiring
# ============================================================
if os.getenv('USE_SQLITE') == '1':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    # SQLite bilan Channel Layers va Celery'ni memory'ga o'tkazish
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    # Celery testlar uchun sinxron rejim
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# ============================================================
# Mahalliy muhit uchun qo'shimcha sozlamalar
# ============================================================

# Django Debug Toolbar (ixtiyoriy — pip install django-debug-toolbar)
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
# INTERNAL_IPS = ['127.0.0.1']

# Mahalliy muhitda CORS'ga ruxsat
CORS_ALLOW_ALL_ORIGINS = True

# Email backend — terminalda ko'rsatish
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
