"""
Local development settings for EduSelf Teacher.
Enables debug mode, relaxed host checks, and developer utilities.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Allow fallback to SQLite if PostgreSQL is not running locally
USE_SQLITE = os.getenv("USE_SQLITE", "True").lower() in ("true", "1", "yes")

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# Development email backend (prints emails to terminal)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Optional debug toolbar or internal IPs
INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]
