# ============================================================
# EduSelf Teacher — core/settings/base.py
# Barcha muhitlar uchun umumiy sozlamalar
# TECH_STACK.md §3 va Backend.md §1 asosida
# ============================================================
import os
from pathlib import Path

# python-dotenv bilan .env faylni yuklash (mahalliy ishlab chiqish uchun)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'replace-me-with-strong-50-char-secret-for-dev-only')

# ============================================================
# O'rnatilgan Ilovalar
# DIQQAT: 'daphne' BIRINCHI bo'lishi shart! (Django Channels talabi)
# ============================================================
INSTALLED_APPS = [
    'daphne',                               # Birinchi! ASGI server (TECH_STACK.md §3.2)
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Uchinchi tomon ilovalar
    'rest_framework',
    'channels',
    'corsheaders',
    # EduSelf ilovalari (Phase 01 dan boshlab qo'shiladi)
    'apps.authentication',    # Phase 01: Foydalanuvchilar va RBAC
    'apps.questions_registry',# Phase 02: 29 xil savol formati registri
    'apps.quizzes',           # Phase 02: Viktorinalar va savollar boshqaruvi
    'apps.game_engine',       # Phase 04: O'yin Rejimlari va Shohsupa
    'apps.live_sessions',     # Phase 03: Real-Time Dvigatel va WebSockets
    'apps.ai_workspace',      # Phase 06: O'qituvchi AI Ish Joyi
    'apps.ai_gateway',        # Phase 05: AI Gateway va BYOK Shifrlash
    'apps.mcp_server',        # Phase 07
    'apps.sheets_sync',       # Phase 09
    # 'apps.analytics',         # Phase 09
]

# ============================================================
# Middleware
# ============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',            # CORS (corsheaders talab qiladi — birinchi bo'lishi kerak)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Xavfsizlik middleware'lari (Phase 10 da qo'shiladi)
    # 'core.middleware.security_headers.SecurityHeadersMiddleware',
    # 'core.middleware.rate_limit.RateLimitMiddleware',
    # 'core.middleware.audit_log.AuditLogMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'          # Django Channels uchun

# ============================================================
# Ma'lumotlar Bazasi — PostgreSQL 16 (psycopg3)
# TECH_STACK.md §5.1: psycopg3 — zamonaviy asinxron drayver
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'eduself'),
        'USER': os.getenv('POSTGRES_USER', 'eduself'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# ============================================================
# Redis va Kesh Qatlami (TECH_STACK.md §5.2)
# ============================================================
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

# Django Channels uchun Redis Channel Layer
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_URL],
            'capacity': 1500,               # Har bir kanaldagi maksimal xabarlar soni
            'expiry': 10,                   # Xabarlar muddati (soniya)
        },
    },
}

# Django-redis orqali kesh (so'rovlarni 80% tejaydi — TECH_STACK.md §5.2)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
        },
        'KEY_PREFIX': 'eduself',
        'TIMEOUT': 300,                     # Default TTL: 5 daqiqa
    }
}

# Sessiyalar Redis'da saqlanadi
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# ============================================================
# Celery Konfiguratsiyasi (TECH_STACK.md §6)
# ============================================================
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/1')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tashkent'
CELERY_ENABLE_UTC = True
# Navbatlar konfiguratsiyasi (Backend.md §6 asosida)
CELERY_TASK_QUEUES = {
    'default': {},
    'high_priority': {},        # Real-time o'yin javoblari
    'sync_sheets': {},          # Google Sheets sinxronlash
    'ai_tasks': {},             # AI quiz generatsiya
}
CELERY_TASK_DEFAULT_QUEUE = 'default'

# ============================================================
# Parol Validatsiya
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom User Model (Phase 01 — Backend.md §2.1)
AUTH_USER_MODEL = 'authentication.User'

# Ijtimoiy Autentifikatsiya Sozlamalari (Phase 01)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON = os.getenv('GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON', '')

# ============================================================
# Xalqarolashtirish (Localization)
# ============================================================
LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_I18N = True
USE_TZ = True

# ============================================================
# Statik va Media Fayllar
# ============================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles'

# ============================================================
# Default Primary Key
# ============================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# Strukturaviy JSON Logging (Architecture.md §7)
# ============================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '{"time": "%(asctime)s", "level": "%(levelname)s", "name": "%(name)s", "message": "%(message)s"}',
            'datefmt': '%Y-%m-%dT%H:%M:%S',
        },
        'verbose': {
            'format': '[{levelname}] {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'channels': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ============================================================
# CORS Sozlamalari (Phase 07 MCP Server uchun asos)
# ============================================================
CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_ALL_ORIGINS = False

# ============================================================
# REST Framework (DRF) — asosiy konfiguratsiya
# ============================================================
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ============================================================
# AI Gateway & BYOK Shifrlash Sozlamalari (Phase 05)
# ============================================================
BYOK_ENCRYPTION_KEY = os.environ.get('BYOK_ENCRYPTION_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

