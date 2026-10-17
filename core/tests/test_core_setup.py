"""
EduSelf Teacher — Phase 00 Core Setup Smoke Tests
Tests to verify:
1. Django settings integrity
2. Daphne ASGI application and ProtocolTypeRouter
3. Celery instance configuration
4. Channel layers configuration
"""
import pytest
from django.conf import settings
from channels.routing import ProtocolTypeRouter
from core.asgi import application as asgi_application
from core.celery import app as celery_app


@pytest.mark.unit
def test_django_settings_loaded():
    """Verify that Django settings are loaded and critical configurations are present."""
    assert settings.INSTALLED_APPS[0] == 'daphne', "daphne must be the FIRST item in INSTALLED_APPS"
    assert 'channels' in settings.INSTALLED_APPS
    assert settings.ASGI_APPLICATION == 'core.asgi.application'
    assert settings.ROOT_URLCONF == 'core.urls'


@pytest.mark.unit
def test_asgi_application_is_protocol_type_router():
    """Verify ASGI application uses modern ProtocolTypeRouter (Channels 4.x)."""
    assert isinstance(asgi_application, ProtocolTypeRouter)
    assert 'http' in asgi_application.application_mapping
    assert 'websocket' in asgi_application.application_mapping


@pytest.mark.unit
def test_celery_application_configured():
    """Verify Celery app name and task autodiscovery."""
    assert celery_app.main == 'eduself_teacher'
    assert celery_app.conf.task_default_queue == 'default'
    assert 'high_priority' in celery_app.conf.task_queues


@pytest.mark.unit
def test_channel_layer_configured():
    """Verify channel layer exists in settings."""
    assert 'default' in settings.CHANNEL_LAYERS
