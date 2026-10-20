import os
import pytest
from unittest.mock import patch, MagicMock
from django.test import Client
from django.conf import settings


@pytest.mark.django_db
class TestHealthEndpoints:
    """Liveness & Readiness Probes (DEPLOYMENT_ARCHITECTURE.md §9)."""

    def test_health_live(self):
        client = Client()
        response = client.get('/health/live/', HTTP_X_TEST_NO_RATE_LIMIT='1')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'alive'
        assert data['service'] == 'eduself-backend'

    def test_health_ready_success(self):
        client = Client()
        response = client.get('/health/ready/', HTTP_X_TEST_NO_RATE_LIMIT='1')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ready'
        assert data['components']['database']['status'] == 'healthy'
        assert data['components']['cache']['status'] == 'healthy'

    @patch('django.db.connection.cursor')
    def test_health_ready_db_failure(self, mock_cursor):
        mock_cursor.side_effect = Exception("Database connection lost")
        client = Client()
        response = client.get('/health/ready/', HTTP_X_TEST_NO_RATE_LIMIT='1')
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'not_ready'
        assert data['components']['database']['status'] == 'unhealthy'

    @patch('django.core.cache.cache.get')
    def test_health_ready_cache_failure(self, mock_get):
        mock_get.return_value = None
        client = Client()
        response = client.get('/health/ready/', HTTP_X_TEST_NO_RATE_LIMIT='1')
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'not_ready'
        assert data['components']['cache']['status'] == 'unhealthy'


class TestDeploymentManifests:
    """Production Docker, Nginx & Shell Script Manifest Validations."""

    @pytest.fixture
    def base_dir(self):
        return settings.BASE_DIR

    def test_dockerfile_backend_structure(self, base_dir):
        dockerfile_path = os.path.join(base_dir, 'deploy', 'Dockerfile.backend')
        assert os.path.exists(dockerfile_path)

        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Multi-stage build
        assert "AS builder" in content
        assert "AS runner" in content
        # Non-root user
        assert "appuser" in content
        assert "USER appuser" in content
        # Port
        assert "EXPOSE 8000" in content
        # Entrypoint
        assert "ENTRYPOINT" in content
        assert "entrypoint.sh" in content

    def test_docker_compose_structure(self, base_dir):
        compose_path = os.path.join(base_dir, 'deploy', 'docker-compose.prod.yml')
        assert os.path.exists(compose_path)

        with open(compose_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 6 Production services
        services = ['nginx:', 'web:', 'celery-worker:', 'celery-beat:', 'postgres:', 'redis:']
        for svc in services:
            assert svc in content, f"{svc} xizmati docker-compose.prod.yml da topilmadi"

        # Network and volumes
        assert "eduself-net" in content
        assert "postgres_data:" in content
        assert "redis_data:" in content
        assert "static_volume:" in content

        # Healthchecks
        assert "healthcheck:" in content
        assert "pg_isready" in content

    def test_nginx_config_structure(self, base_dir):
        conf_path = os.path.join(base_dir, 'deploy', 'nginx', 'conf.d', 'eduself.conf')
        assert os.path.exists(conf_path)

        with open(conf_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # WebSockets upgrade
        assert "location /ws/" in content
        assert "Upgrade $http_upgrade" in content
        assert 'Connection "upgrade"' in content
        assert "proxy_read_timeout 3600s" in content

        # SSE streaming
        assert "location /mcp/" in content
        assert "proxy_buffering off" in content

        # Static files caching
        assert "location /static/" in content
        assert "expires 30d" in content

        # Health checks
        assert "location /health/" in content

    def test_shell_scripts_exist_and_valid(self, base_dir):
        scripts_dir = os.path.join(base_dir, 'deploy', 'scripts')

        entrypoint = os.path.join(scripts_dir, 'entrypoint.sh')
        backup = os.path.join(scripts_dir, 'backup_db.sh')
        restore = os.path.join(scripts_dir, 'restore_db.sh')

        assert os.path.exists(entrypoint)
        assert os.path.exists(backup)
        assert os.path.exists(restore)

        with open(entrypoint, 'r', encoding='utf-8') as f:
            ep_content = f.read()
            assert "#!/usr/bin/env bash" in ep_content
            assert "migrate" in ep_content
            assert "collectstatic" in ep_content

        with open(backup, 'r', encoding='utf-8') as f:
            bk_content = f.read()
            assert "pg_dump" in bk_content
            assert "gzip" in bk_content
            assert "-mtime +7 -delete" in bk_content

        with open(restore, 'r', encoding='utf-8') as f:
            rst_content = f.read()
            assert "psql" in rst_content
