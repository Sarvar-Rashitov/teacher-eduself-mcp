"""
Base settings for EduSelf Teacher project.
Shared across all environments (local, staging, production).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# Security Warning: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-eduself-teacher-local-development-secret-key-2026'
)

DEBUG = False
ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    # Daphne ASGI server must be listed before staticfiles
    'daphne',

    # Jazzmin Admin Theme (must be before django.contrib.admin)
    'jazzmin',

    # Django Core Applications
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third Party Applications
    'channels',
    'rest_framework',
    'django_celery_beat',
    'corsheaders',

    # Local Applications
    'apps.authentication',          # Phase 01: Auth & RBAC
    'apps.questions_registry',      # Phase 02: 29 Question Formats Registry
    'apps.quizzes',                 # Phase 02: Quiz & Question CRUD & Engine
    'apps.live_sessions',           # Phase 03: Real-Time Engine, WebSockets & FSM
    'apps.game_engine',             # Phase 04: Game Modes Catalog & Engine
    'apps.ai_gateway',              # Phase 05: Multi-Provider AI Gateway & BYOK
    'apps.ai_workspace',            # Phase 06: Teacher AI Agent & Quiz Generation
    'apps.mcp_server',              # Phase 07: Model Context Protocol (MCP) Server
    'apps.sheets_sync',             # Phase 09: Google Sheets Sync & Celery Tasks
]

# Custom User Model (Phase 01)
AUTH_USER_MODEL = 'authentication.User'

# Social Authentication Settings (Telegram & Google)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'core.middleware.security_headers.SecurityHeadersMiddleware',
    'core.middleware.rate_limit.SlidingWindowRateLimitMiddleware',
    'core.middleware.audit_log.AuditLogMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
ASGI_APPLICATION = 'core.asgi.application'

# Channel Layers Configuration (Redis Pub/Sub)
REDIS_CHANNEL_URL = os.getenv('REDIS_CHANNEL_URL', 'redis://localhost:6379/1')
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [REDIS_CHANNEL_URL],
        },
    },
}

# Cache Configuration (django-redis)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
        }
    }
}

# Celery Configuration
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/2')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tashkent'
CELERY_ENABLE_UTC = True

# Password Hashing (Argon2id preferred per SECURITY.md)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = os.getenv('DEFAULT_LOCALE', 'uz-Latn')
TIME_ZONE = os.getenv('TIME_ZONE', 'Asia/Tashkent')
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = []
if (BASE_DIR / 'static').exists():
    STATICFILES_DIRS.append(BASE_DIR / 'static')

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# AI Gateway & BYOK Encryption Settings (Phase 05)
BYOK_ENCRYPTION_KEY = os.getenv('BYOK_ENCRYPTION_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')

# Google Sheets Synchronization (Phase 09)
GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON = os.getenv('GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON', '')
GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE', '')

# Celery Task Queue Settings
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'))
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'))
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() in ('true', '1', 't')

# Password Hashers (OWASP A07 - Argon2id by default)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL_ORIGINS', 'False').lower() in ('true', '1', 't')
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,https://eduself.uz').split(',')
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

# Security Headers & OWASP Hardening Defaults
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ==============================================================================
# Django Jazzmin Administration Theme Configuration
# ==============================================================================
JAZZMIN_SETTINGS = {
    # Title on the window
    "site_title": "EduSelf Admin",

    # Title on the login screen (19 chars max)
    "site_header": "EduSelf",

    # Title on the brand (19 chars max)
    "site_brand": "EduSelf Teacher",

    # Logo to use for your site, must be present in static files
    "site_logo": "img/icons/sparkles.svg",

    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",

    # Relative path to a favicon for your site
    "site_icon": "img/icons/sparkles.svg",

    # Welcome text on the login screen
    "welcome_sign": "EduSelf Teacher Boshqaruv Tizimiga Xush Kelibsiz",

    # Copyright on the footer
    "copyright": "EduSelf Teacher Platform",

    # List of model admins to search from the search bar
    "search_model": ["authentication.User", "quizzes.Quiz"],

    ############
    # Top Menu #
    ############
    "topmenu_links": [
        {"name": "Asosiy Sahifa", "url": "home", "icon": "fas fa-home", "permissions": ["auth.view_user"]},
        {"name": "O‘qituvchi Boshqaruvi", "url": "dashboard", "icon": "fas fa-chalkboard-teacher"},
        {"model": "authentication.User", "icon": "fas fa-user-shield"},
        {"model": "quizzes.Quiz", "icon": "fas fa-brain"},
    ],

    #############
    # User Menu #
    #############
    "usermenu_links": [
        {"name": "EduSelf Dashboard", "url": "dashboard", "icon": "fas fa-tachometer-alt"},
    ],

    #############
    # Side Menu #
    #############
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    "order_with_respect_to": [
        "authentication",
        "quizzes",
        "live_sessions",
        "game_engine",
        "ai_workspace",
        "ai_gateway",
        "mcp_server",
        "sheets_sync",
        "django_celery_beat",
        "auth",
    ],

    # Custom icons for side menu apps and models (FontAwesome 5 & 6)
    "icons": {
        # App Icons
        "auth": "fas fa-shield-alt",
        "authentication": "fas fa-user-lock",
        "quizzes": "fas fa-brain",
        "live_sessions": "fas fa-broadcast-tower",
        "game_engine": "fas fa-gamepad",
        "ai_gateway": "fas fa-microchip",
        "ai_workspace": "fas fa-robot",
        "mcp_server": "fas fa-network-wired",
        "sheets_sync": "fas fa-table",
        "django_celery_beat": "fas fa-clock",

        # Authentication Models
        "authentication.user": "fas fa-user-shield",
        "authentication.User": "fas fa-user-shield",
        "authentication.organization": "fas fa-school",
        "authentication.Organization": "fas fa-school",
        "authentication.teacherprofile": "fas fa-id-card",
        "authentication.TeacherProfile": "fas fa-id-card",

        # Quizzes Models
        "quizzes.quiz": "fas fa-brain",
        "quizzes.Quiz": "fas fa-brain",
        "quizzes.question": "fas fa-question-circle",
        "quizzes.Question": "fas fa-question-circle",
        "quizzes.quizversion": "fas fa-code-branch",
        "quizzes.QuizVersion": "fas fa-code-branch",

        # Live Sessions Models
        "live_sessions.livesession": "fas fa-gamepad",
        "live_sessions.LiveSession": "fas fa-gamepad",
        "live_sessions.participant": "fas fa-users",
        "live_sessions.Participant": "fas fa-users",
        "live_sessions.answersubmission": "fas fa-check-double",
        "live_sessions.AnswerSubmission": "fas fa-check-double",

        # AI Gateway Models
        "ai_gateway.userapikey": "fas fa-key",
        "ai_gateway.UserApiKey": "fas fa-key",
        "ai_gateway.tokenusagelog": "fas fa-chart-line",
        "ai_gateway.TokenUsageLog": "fas fa-chart-line",
        "ai_gateway.aiproviderkey": "fas fa-key",
        "ai_gateway.aiusagelog": "fas fa-chart-line",

        # Sheets Sync Models
        "sheets_sync.sheetmapping": "fas fa-file-excel",
        "sheets_sync.SheetMapping": "fas fa-file-excel",
        "sheets_sync.sheetsynclog": "fas fa-history",
        "sheets_sync.SheetSyncLog": "fas fa-history",
        "sheets_sync.googlesheetsync": "fas fa-file-excel",

        # Django Celery Beat Models
        "django_celery_beat.periodictask": "fas fa-tasks",
        "django_celery_beat.PeriodicTask": "fas fa-tasks",
        "django_celery_beat.crontabschedule": "fas fa-calendar-alt",
        "django_celery_beat.CrontabSchedule": "fas fa-calendar-alt",
        "django_celery_beat.intervalschedule": "fas fa-stopwatch",
        "django_celery_beat.IntervalSchedule": "fas fa-stopwatch",
        "django_celery_beat.clockedschedule": "fas fa-bell",
        "django_celery_beat.ClockedSchedule": "fas fa-bell",
        "django_celery_beat.solarschedule": "fas fa-sun",
        "django_celery_beat.SolarSchedule": "fas fa-sun",

        # Auth Groups
        "auth.group": "fas fa-users-cog",
        "auth.Group": "fas fa-users-cog",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-layer-group",

    #################
    # Related Modal #
    #################
    "related_modal_active": True,

    #############
    # UI Tweaks #
    #############
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "authentication.User": "collapsible",
        "quizzes.Quiz": "vertical_tabs",
    },
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-orange",
    "accent": "accent-orange",
    "navbar": "navbar-dark navbar-orange",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-warning",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-warning",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

