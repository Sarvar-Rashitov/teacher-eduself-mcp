# ============================================================
# EduSelf Teacher — apps/mcp_server/tests/test_transports.py
# Tests for HTTP SSE & JSON-RPC Dispatcher
# ============================================================
import json
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.mcp_server.auth import generate_access_token

User = get_user_model()


@pytest.fixture
def teacher(db):
    return User.objects.create_user(
        username="mcp_transport_teacher",
        password="password123",
        role="teacher"
    )


@pytest.fixture
def auth_token(teacher):
    return generate_access_token(teacher, scopes=[
        "quiz:read", "quiz:write", "session:create", "session:control", "session:read", "report:read"
    ])


@pytest.mark.django_db
class TestSSEAndMessagesTransports:
    def test_sse_endpoint_connects(self, client, auth_token):
        response = client.get("/mcp/sse/", HTTP_AUTHORIZATION=f"Bearer {auth_token}")
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/event-stream'

    def test_sse_endpoint_unauthorized(self, client):
        response = client.get("/mcp/sse/")
        assert response.status_code == 401

    def test_jsonrpc_initialize(self, client, auth_token):
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Claude Desktop", "version": "1.0"}
            }
        }
        response = client.post(
            "/mcp/messages/",
            data=json.dumps(init_req),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {auth_token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert data["result"]["serverInfo"]["name"] == "eduself-teacher-mcp"
        assert "tools" in data["result"]["capabilities"]

    def test_jsonrpc_tools_list(self, client, auth_token):
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        response = client.post(
            "/mcp/messages/",
            data=json.dumps(list_req),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {auth_token}"
        )
        assert response.status_code == 200
        data = response.json()
        tools = data["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "create_quiz_draft" in tool_names
        assert "create_live_session" in tool_names
        assert "get_session_report" in tool_names

    def test_jsonrpc_tools_call_create_quiz(self, client, auth_token):
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "create_quiz_draft",
                "arguments": {
                    "title": "SSE JSON-RPC Quiz",
                    "subject": "Fizika",
                    "grade_level": 9,
                    "topic": "Mexanika"
                }
            }
        }
        response = client.post(
            "/mcp/messages/",
            data=json.dumps(call_req),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {auth_token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" not in data
        assert "quiz_id" in data["result"] or "result" in data

    def test_jsonrpc_unknown_method_returns_error(self, client, auth_token):
        unknown_req = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "non_existent_method",
            "params": {}
        }
        response = client.post(
            "/mcp/messages/",
            data=json.dumps(unknown_req),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {auth_token}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601  # Method Not Found
