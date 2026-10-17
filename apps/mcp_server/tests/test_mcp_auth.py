# ============================================================
# EduSelf Teacher — apps/mcp_server/tests/test_mcp_auth.py
# Unit Tests for OAuth 2.1 PKCE, Bearer Tokens & Scopes
# ============================================================
import base64
import hashlib
import json
import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from apps.mcp_server.auth import (
    authenticate_token,
    generate_access_token,
    verify_pkce,
    set_current_mcp_context,
    reset_current_mcp_context,
    MCPContext,
)
from apps.mcp_server.exceptions import MCPUnauthorizedError, MCPForbiddenError
from apps.mcp_server.models import MCPApiToken, MCPOAuthAuthorizationCode, MCPClient
from apps.mcp_server.scopes import require_scope

User = get_user_model()


@pytest.mark.django_db
class TestPKCEVerification:
    def test_pkce_s256_success(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        digest = hashlib.sha256(verifier.encode('ascii')).digest()
        challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')

        assert verify_pkce(verifier, challenge, 'S256') is True

    def test_pkce_s256_failure(self):
        verifier = "valid_verifier_string_123456789012345"
        wrong_challenge = "totally_wrong_challenge_string"
        assert verify_pkce(verifier, wrong_challenge, 'S256') is False

    def test_pkce_plain_mode(self):
        string_val = "plain_secret_string"
        assert verify_pkce(string_val, string_val, 'plain') is True
        assert verify_pkce(string_val, "different", 'plain') is False


@pytest.mark.django_db
class TestTokenAuthentication:
    @pytest.fixture
    def teacher(self):
        return User.objects.create_user(
            username="teacher_auth_test",
            password="secure_password_123",
            role="teacher"
        )

    def test_generate_and_authenticate_jwt_bearer(self, teacher):
        scopes = ["quiz:read", "quiz:write"]
        token = generate_access_token(teacher, scopes=scopes, expires_in=3600)

        # Bearer prefiksi bilan tekshirish
        ctx = authenticate_token(f"Bearer {token}")
        assert ctx.user.id == teacher.id
        assert ctx.token_type == "bearer"
        assert "quiz:read" in ctx.scopes
        assert "quiz:write" in ctx.scopes

    def test_expired_jwt_token_raises_unauthorized(self, teacher):
        token = generate_access_token(teacher, expires_in=-10)  # Muddati o'tgan
        with pytest.raises(MCPUnauthorizedError):
            authenticate_token(token)

    def test_tampered_jwt_token_raises_unauthorized(self, teacher):
        token = generate_access_token(teacher, expires_in=3600)
        tampered = token[:-5] + "ABCDE"
        with pytest.raises(MCPUnauthorizedError):
            authenticate_token(tampered)

    def test_api_token_success(self, teacher):
        token_str = "usr_token_test_1234567890abcdef1234567890"
        MCPApiToken.objects.create(
            user=teacher,
            name="Claude Desktop Key",
            token=token_str,
            scopes="quiz:read session:create",
            is_active=True
        )

        ctx = authenticate_token(token_str)
        assert ctx.user.id == teacher.id
        assert ctx.token_type == "api_token"
        assert "quiz:read" in ctx.scopes
        assert "session:create" in ctx.scopes

    def test_inactive_api_token_fails(self, teacher):
        token_str = "usr_token_inactive_123"
        MCPApiToken.objects.create(
            user=teacher,
            token=token_str,
            is_active=False
        )
        with pytest.raises(MCPUnauthorizedError):
            authenticate_token(token_str)

    def test_expired_api_token_fails(self, teacher):
        token_str = "usr_token_expired_123"
        MCPApiToken.objects.create(
            user=teacher,
            token=token_str,
            is_active=True,
            expires_at=timezone.now() - timedelta(days=1)
        )
        with pytest.raises(MCPUnauthorizedError):
            authenticate_token(token_str)


@pytest.mark.django_db
class TestScopeDecorator:
    @pytest.fixture
    def teacher(self):
        return User.objects.create_user(
            username="scope_test_user",
            password="testpassword",
            role="teacher"
        )

    def test_require_scope_allowed(self, teacher):
        ctx = MCPContext(user=teacher, scopes=["quiz:read", "quiz:write"])
        token = set_current_mcp_context(ctx)

        @require_scope("quiz:read")
        def protected_view():
            return "SUCCESS"

        try:
            assert protected_view() == "SUCCESS"
        finally:
            reset_current_mcp_context(token)

    def test_require_scope_denied(self, teacher):
        ctx = MCPContext(user=teacher, scopes=["quiz:read"])  # quiz:write yo'q
        token = set_current_mcp_context(ctx)

        @require_scope("quiz:write")
        def protected_write():
            return "SUCCESS"

        try:
            with pytest.raises(MCPForbiddenError):
                protected_write()
        finally:
            reset_current_mcp_context(token)


@pytest.mark.django_db
class TestOAuthEndpoints:
    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def teacher(self):
        return User.objects.create_user(
            username="oauth_flow_user",
            password="secure_password",
            role="teacher"
        )

    def test_oauth_pkce_end_to_end_flow(self, client, teacher):
        # 1. code_verifier va code_challenge tayyorlaymiz
        verifier = "sample_pkce_verifier_string_1234567890"
        digest = hashlib.sha256(verifier.encode('ascii')).digest()
        challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')

        # 2. GET /oauth/authorize/
        auth_url = f"/oauth/authorize/?client_id=claude-client&redirect_uri=http://localhost:8085/callback&response_type=code&code_challenge={challenge}&code_challenge_method=S256&username={teacher.username}&state=xyz123"
        resp = client.get(auth_url)
        assert resp.status_code == 302
        redirect_url = resp.headers['Location']
        assert "code=" in redirect_url
        assert "state=xyz123" in redirect_url

        # Kodni ajratib olamiz
        code = redirect_url.split("code=")[1].split("&")[0]

        # 3. POST /oauth/token/
        token_resp = client.post("/oauth/token/", {
            "grant_type": "authorization_code",
            "client_id": "claude-client",
            "code": code,
            "redirect_uri": "http://localhost:8085/callback",
            "code_verifier": verifier,
        })
        assert token_resp.status_code == 200
        data = token_resp.json()
        assert "access_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 3600
        assert "refresh_token" in data

        # Token orqali tekshirish
        ctx = authenticate_token(data["access_token"])
        assert ctx.user.id == teacher.id
