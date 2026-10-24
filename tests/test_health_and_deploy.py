"""
Tests for Production Health Probes, Nginx, Dockerfiles, and Deployment Scripts.
According to Phase 11 and DEPLOYMENT_ARCHITECTURE.md.
"""

import os
import pytest
import yaml
from unittest.mock import patch, MagicMock
from django.test import Client


@pytest.mark.django_db
def test_health_liveness_endpoints():
    """Liveness tekshiruvi: /health/ va /health/live/ HTTP 200 qaytarishi kerak."""
    client = Client()

    resp_root = client.get("/health/")
    assert resp_root.status_code == 200
    data_root = resp_root.json()
    assert data_root["status"] == "live"
    assert "EduSelf Teacher Core" in data_root["service"]

    resp_live = client.get("/health/live/")
    assert resp_live.status_code == 200
    assert resp_live.json()["status"] == "live"


@pytest.mark.django_db
def test_health_readiness_healthy():
    """Readiness tekshiruvi: DB va Cache ishlaganda HTTP 200 qaytarishi kerak."""
    client = Client()

    resp = client.get("/health/ready/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "connected"
    assert data["checks"]["cache"] == "connected"


@pytest.mark.django_db
def test_health_readiness_database_failure():
    """Baza uzilganda Readiness tekshiruvi HTTP 503 qaytarishi kerak."""
    client = Client()

    with patch("django.db.connection.cursor") as mock_cursor:
        mock_cursor.side_effect = Exception("DB Connection refused")
        resp = client.get("/health/ready/")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"] == "disconnected"


@pytest.mark.django_db
def test_health_readiness_cache_failure():
    """Kesh uzilganda Readiness tekshiruvi HTTP 503 qaytarishi kerak."""
    client = Client()

    with patch("django.core.cache.cache.set") as mock_cache_set:
        mock_cache_set.side_effect = Exception("Redis connection timed out")
        resp = client.get("/health/ready/")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["cache"] == "disconnected"


def test_dockerfile_backend_security_and_structure():
    """Dockerfile.backend xavfsizlik talablariga (non-root, multi-stage) javob berishini tekshirish."""
    dockerfile_path = os.path.join("deploy", "Dockerfile.backend")
    assert os.path.exists(dockerfile_path), "deploy/Dockerfile.backend mavjud emas!"

    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Multi-stage tekshiruvi
    assert "AS builder" in content, "Dockerfile multi-stage 'builder' bosqichiga ega bo'lishi shart!"
    assert "AS runner" in content, "Dockerfile multi-stage 'runner' bosqichiga ega bo'lishi shart!"

    # Non-root user tekshiruvi (Self-Audit talabi)
    assert "useradd" in content or "adduser" in content
    assert "USER appuser" in content, "Ishlab chiqarish konteyneri non-root user (appuser) ostida ishlashi shart!"

    # Healthcheck tekshiruvi
    assert "HEALTHCHECK" in content, "Dockerfile ichida HEALTHCHECK belgisi bo'lishi shart!"
    assert "entrypoint.sh" in content


def test_nginx_conf_websocket_and_security():
    """Nginx konfiguratsiyasida WebSocket va SSE to'g'ri sozlanganligini tekshirish."""
    nginx_path = os.path.join("deploy", "nginx", "nginx.conf")
    assert os.path.exists(nginx_path), "deploy/nginx/nginx.conf mavjud emas!"

    with open(nginx_path, "r", encoding="utf-8") as f:
        content = f.read()

    # WebSocket Upgrade (Self-audit talabi)
    assert "proxy_set_header Upgrade $http_upgrade;" in content
    assert 'proxy_set_header Connection "upgrade";' in content
    assert "proxy_read_timeout 3600s;" in content, "WebSocket 1 soatlik taymoutga ega bo'lishi kerak!"

    # SSL va HTTP/2
    assert "ssl_protocols" in content
    assert "TLSv1.2 TLSv1.3" in content
    assert "http2 on" in content or "listen 443 ssl http2" in content

    # Statik va Media tarqatish
    assert "location /static/" in content
    assert "location /media/" in content

    # MCP SSE
    assert "location /mcp/" in content
    assert "proxy_buffering off;" in content


def test_docker_compose_prod_validity():
    """docker-compose.prod.yml fayli to'g'ri sintaksisga va barcha zaruriy servislarga ega bo'lishini tekshirish."""
    compose_path = os.path.join("deploy", "docker-compose.prod.yml")
    assert os.path.exists(compose_path), "deploy/docker-compose.prod.yml topilmadi!"

    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    required_services = ["nginx", "backend", "celery-worker", "celery-beat", "redis", "postgres"]

    for s in required_services:
        assert s in services, f"docker-compose.prod.yml da '{s}' xizmati mavjud emas!"

    # Healthcheck tekshiruvi
    assert "healthcheck" in services["postgres"]
    assert "healthcheck" in services["redis"]
    assert "healthcheck" in services["backend"]


def test_backup_and_restore_scripts():
    """Zaxira nusxalash (backup_db.sh) va qayta tiklash (restore_db.sh) skriptlarini tekshirish."""
    backup_script = os.path.join("deploy", "scripts", "backup_db.sh")
    restore_script = os.path.join("deploy", "scripts", "restore_db.sh")
    entrypoint_script = os.path.join("deploy", "scripts", "entrypoint.sh")

    assert os.path.exists(backup_script), "backup_db.sh topilmadi!"
    assert os.path.exists(restore_script), "restore_db.sh topilmadi!"
    assert os.path.exists(entrypoint_script), "entrypoint.sh topilmadi!"

    with open(backup_script, "r", encoding="utf-8") as f:
        content = f.read()

    # pg_dump, siqish va avtomatik eski fayllarni tozalash (Self-Audit talabi)
    assert "pg_dump" in content
    assert "-Fc" in content
    assert "find" in content and "-mtime" in content, "Eski zaxira fayllarni tozalash mantig'i mavjud bo'lishi shart!"
