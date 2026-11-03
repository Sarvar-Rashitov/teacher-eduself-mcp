"""
Local development settings for EduSelf Teacher project.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')
if '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('*')

# Database Configuration
if os.getenv('USE_SQLITE', 'False').lower() == 'true':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'eduself_db'),
            'USER': os.getenv('POSTGRES_USER', 'eduself_user'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'eduself_secret_password'),
            'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', '5432'),
        }
    }

# Option for in-memory channel layer during lightweight unit testing
if os.getenv('USE_IN_MEMORY_CHANNELS', 'False').lower() == 'true':
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Option for in-memory cache when running with SQLite locally / unit testing
if os.getenv('USE_SQLITE', 'False').lower() == 'true':
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'eduself-local-cache',
        }
    }

# Celery local development & testing defaults
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'True').lower() in ('true', '1', 't')
CELERY_TASK_EAGER_PROPAGATES = True

