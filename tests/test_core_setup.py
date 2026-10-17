import importlib
import pytest
from pathlib import Path
from django.conf import settings
from channels.layers import get_channel_layer
from core.celery import app as celery_app
from core.asgi import application as asgi_application


def test_django_settings_loaded():
    """Verify that Django settings are properly loaded."""
    assert settings.ROOT_URLCONF == 'core.urls'
    assert 'daphne' in settings.INSTALLED_APPS
    assert 'channels' in settings.INSTALLED_APPS
    assert 'rest_framework' in settings.INSTALLED_APPS
    assert settings.TIME_ZONE == 'Asia/Tashkent'
    assert settings.LANGUAGE_CODE == 'uz-Latn'


def test_celery_app_configured():
    """Verify that Celery app is properly registered."""
    assert celery_app.main == 'eduself'
    assert celery_app.conf.timezone == 'Asia/Tashkent'
    assert celery_app.conf.task_serializer == 'json'


def test_asgi_application_configured():
    """Verify ASGI protocol router is ready."""
    assert asgi_application is not None


def test_channel_layer_configured():
    """Verify that Channel layer is configured and accessible."""
    channel_layer = get_channel_layer()
    assert channel_layer is not None


def test_required_directories_exist():
    """Verify templates, static, and apps directories exist."""
    base_dir = Path(settings.BASE_DIR)
    assert (base_dir / 'templates').is_dir()
    assert (base_dir / 'static').is_dir()
    assert (base_dir / 'apps').is_dir()


def test_production_settings_module():
    """Verify that production settings module can be imported cleanly without syntax errors."""
    prod_module = importlib.import_module('core.settings.production')
    assert prod_module.DEBUG is False
    assert prod_module.SECURE_BROWSER_XSS_FILTER is True
    assert prod_module.X_FRAME_OPTIONS == 'DENY'
