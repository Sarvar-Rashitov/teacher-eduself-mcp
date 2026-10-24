"""
Production settings for EduSelf Teacher.
Enforces SSL, security headers, and production-grade caching and logging.
"""

from .base import *

DEBUG = False

# Production Secret Key
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "eduself-teacher-production-super-secret-key-must-be-configured-in-env-at-least-50-chars-long",
)

# Strict SSL and cookie security
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() in ("true", "1", "yes")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# HTTP Strict Transport Security (HSTS)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", 31536000))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Production Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
