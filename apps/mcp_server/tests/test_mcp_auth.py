"""
Unit & Integration Tests for MCP Authentication and Authorization Scopes (DOC-84, DOC-85).
"""

import pytest
import json
from django.contrib.auth import get_user_model
from django.test import Client
from apps.authentication.models import Organization
from apps.mcp_server.auth import (
    generate_mcp_token,
    verify_mcp_token,
    authenticate_header,
    MCPAuthContextManager,
    get_current_mcp_context,
)
from apps.mcp_server.scopes import Scopes, require_scope
from apps.mcp_server.exceptions import MCPUnauthorizedError, MCPForbiddenError

User = get_user_model()


@pytest.mark.django_db
class TestMCPAuthentication:
    @pytest.fixture(autouse=True)
    def setup_users(self):
        self.org = Organization.objects.create(name="1-Maktab", subscription_plan="school")
        self.teacher = User.objects.create_user(
            username="teacher_rustam",
            email="rustam@eduself.uz",
            password="testpassword123",
            organization=self.org,
            role="teacher",
        )
        self.other_teacher = User.objects.create_user(
            username="teacher_dilnoza",
            email="dilnoza@eduself.uz",
            password="testpassword123",
            role="teacher",
        )
        self.client = Client()

    def test_token_generation_and_verification_roundtrip(self):
        """Token to'g'ri yaratilishi va muvaffaqiyatli dekodlanishi kerak."""
        scopes = [Scopes.QUIZ_READ, Scopes.QUIZ_WRITE, Scopes.SESSION_CREATE]
        token = generate_mcp_token(self.teacher, scopes=scopes, expires_in_seconds=3600)
        assert isinstance(token, str)

        ctx = verify_mcp_token(f"Bearer {token}")
        assert ctx.user.id == self.teacher.id
        assert ctx.teacher_id == str(self.teacher.id)
        assert ctx.has_scope(Scopes.QUIZ_READ)
        assert ctx.has_scope(Scopes.QUIZ_WRITE)
        assert not ctx.has_scope(Scopes.REPORT_READ)

    def test_expired_token_raises_unauthorized(self):
        """Muddati o'tgan token rad etilishi shart."""
        expired_token = generate_mcp_token(self.teacher, scopes=[Scopes.QUIZ_READ], expires_in_seconds=-10)
        with pytest.raises(MCPUnauthorizedError) as exc_info:
            verify_mcp_token(expired_token)
        assert "muddati tugagan" in str(exc_info.value).lower()

    def test_tampered_token_raises_unauthorized(self):
        """Soxtalashtirilgan token rad etilishi shart."""
        token = generate_mcp_token(self.teacher, scopes=[Scopes.QUIZ_READ])
        tampered = token[:-5] + "abcde"
        with pytest.raises(MCPUnauthorizedError):
            verify_mcp_token(tampered)

    def test_inactive_user_raises_forbidden(self):
        """Muzlatilgan yoki o'chirilgan foydalanuvchi hisobi to'siladi."""
        self.teacher.is_active = False
        self.teacher.save()
        token = generate_mcp_token(self.teacher, scopes=[Scopes.QUIZ_READ])
        with pytest.raises(MCPForbiddenError):
            verify_mcp_token(token)

    def test_require_scope_decorator_enforcement(self):
        """@require_scope dekoratori ruxsat yetarli bo'lmaganda 403 chiqarishi shart."""
        @require_scope(Scopes.SESSION_CONTROL)
        def dummy_action():
            return "SUCCESS"

        # 1. Scope yetarli bo'lmaganda
        with MCPAuthContextManager(user=self.teacher, scopes=[Scopes.QUIZ_READ]):
            with pytest.raises(MCPForbiddenError) as exc:
                dummy_action()
            assert "session:control" in str(exc.value)

        # 2. To'g'ri scope bilan
        with MCPAuthContextManager(user=self.teacher, scopes=[Scopes.SESSION_CONTROL]):
            res = dummy_action()
            assert res == "SUCCESS"

    def test_http_endpoint_without_auth_returns_401(self):
        """Authorization header'siz POST /mcp/messages so'rovi 401 qaytaradi."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        }
        response = self.client.post(
            "/mcp/messages",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == -32001

    def test_http_endpoint_with_valid_token_returns_200(self):
        """To'g'ri Bearer token bilan /mcp/messages JSON-RPC javob qaytaradi."""
        token = generate_mcp_token(self.teacher, scopes=list(Scopes.ALL))
        payload = {
            "jsonrpc": "2.0",
            "id": 100,
            "method": "initialize",
        }
        response = self.client.post(
            "/mcp/messages",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 100
        assert data["result"]["serverInfo"]["name"] == "eduself-teacher-mcp"
