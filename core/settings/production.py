# ============================================================
# EduSelf Teacher — core/settings/production.py
# AWS EC2 ishlab chiqarish sozlamalari (Phase 11 da to'liq kengaytiriladi)
# Backend.md §1.1 asosida
# ============================================================
import os
from .base import *

DEBUG = False

ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost').split(',')

# ============================================================
# Xavfsizlik sozlamalari (Phase 10 da to'liq kengaytiriladi)
# ============================================================

# HTTPS majburiy
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000             # 1 yil
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Brauzer xavfsizlik sozlamalari
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Cookie xavfsizligi
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# ============================================================
# Ishlab chiqarish ma'lumotlar bazasi — faqat env o'zgaruvchilardan
# SQLite fallback yo'q!
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['POSTGRES_DB'],
        'USER': os.environ['POSTGRES_USER'],
        'PASSWORD': os.environ['POSTGRES_PASSWORD'],
        'HOST': os.environ['POSTGRES_HOST'],
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# ============================================================
# Email (Phase 11 da konfiguratsiya qilinadi)
# ============================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
