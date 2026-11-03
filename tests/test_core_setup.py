"""
Unit tests verifying Phase 00 core configuration and infrastructure readiness.
"""

import pytest
from django.conf import settings
from core.asgi import application as asgi_app
from core.wsgi import application as wsgi_app
from core.celery import app as celery_app


def test_django_settings_loaded():
    """Verify that Django settings are properly loaded."""
    assert settings.configured is True
    assert 'core.settings' in settings.SETTINGS_MODULE
    assert 'daphne' in settings.INSTALLED_APPS
    assert 'channels' in settings.INSTALLED_APPS
    assert settings.TIME_ZONE == 'Asia/Tashkent'
    assert settings.LANGUAGE_CODE == 'uz-Latn'


def test_daphne_is_first_installed_app():
    """Daphne must be the very first app in INSTALLED_APPS for Channels."""
    assert settings.INSTALLED_APPS[0] == 'daphne'


def test_asgi_application_initialized():
    """Verify ASGI application is callable."""
    assert asgi_app is not None
    assert callable(asgi_app)


def test_wsgi_application_initialized():
    """Verify WSGI application is callable."""
    assert wsgi_app is not None
    assert callable(wsgi_app)


def test_celery_app_configured():
    """Verify Celery app instance configuration."""
    assert celery_app.main == 'eduself'
    assert celery_app.conf.timezone == 'Asia/Tashkent'
    assert 'redis' in celery_app.conf.broker_url
