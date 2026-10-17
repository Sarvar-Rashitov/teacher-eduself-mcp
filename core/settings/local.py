import os
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Database
# If POSTGRES_HOST is provided and USE_SQLITE is not explicitly set, use PostgreSQL.
# Otherwise fallback to SQLite for immediate local testing and lightweight dev.
use_postgres = os.getenv('USE_POSTGRES', 'False').lower() in ('true', '1')

if use_postgres:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'eduself_db'),
            'USER': os.getenv('POSTGRES_USER', 'eduself_user'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'eduself_password'),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# In local/testing mode, fallback to InMemoryChannelLayer if Redis is not running
if os.getenv('USE_IN_MEMORY_CHANNEL_LAYER', 'False').lower() in ('true', '1'):
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
