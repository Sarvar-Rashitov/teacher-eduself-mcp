import json
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.mcp_server.auth import MCPContext, mcp_context_scope, generate_mcp_token
from apps.mcp_server.scopes import TEACHER_DEFAULT_SCOPES
from apps.mcp_server.transports.sse import JSONRPCDispatcher, generate_openapi_spec
from apps.mcp_server.exceptions import CODE_METHOD_NOT_FOUND


User = get_user_model()


@pytest.fixture
def api_teacher(db):
    return User.objects.create_user(
        username="mcp_teacher_api",
        email="teacher_api@eduself.uz",
        role="TEACHER",
    )


@pytest.fixture
def auth_header(api_teacher):
    token = generate_mcp_token(api_teacher)
    return f"Bearer {token}"


def test_jsonrpc_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    }
    resp = JSONRPCDispatcher.handle_request(req)
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "eduself-teacher-mcp"


def test_jsonrpc_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = JSONRPCDispatcher.handle_request(req)
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert len(tools) == 17
    assert "create_quiz_draft" in tool_names
    assert "start_session" in tool_names
    assert "get_session_report" in tool_names

    # destructiveHint tekshiruvi
    start_tool = next(t for t in tools if t["name"] == "start_session")
    assert start_tool["annotations"]["destructiveHint"] is True


def test_jsonrpc_resources_and_prompts_list():
    r_req = {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}}
    r_resp = JSONRPCDispatcher.handle_request(r_req)
    assert len(r_resp["result"]["resources"]) >= 3

    p_req = {"jsonrpc": "2.0", "id": 4, "method": "prompts/list", "params": {}}
    p_resp = JSONRPCDispatcher.handle_request(p_req)
    assert len(p_resp["result"]["prompts"]) == 3


def test_jsonrpc_method_not_found():
    req = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "unknown_metod_xyz",
        "params": {},
    }
    resp = JSONRPCDispatcher.handle_request(req)
    assert resp["id"] == 99
    assert resp["error"]["code"] == CODE_METHOD_NOT_FOUND


@pytest.mark.django_db
def test_jsonrpc_tools_call_execution(api_teacher):
    ctx = MCPContext(user=api_teacher, scopes=TEACHER_DEFAULT_SCOPES.copy())
    with mcp_context_scope(ctx):
        req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "create_quiz_draft",
                "arguments": {
                    "title": "Adabiyot 8-sinf",
                    "subject": "Adabiyot",
                    "grade_level": 8,
                },
            },
        }
        resp = JSONRPCDispatcher.handle_request(req)
        assert resp["id"] == 10
        assert resp["result"]["isError"] is False
        content_text = resp["result"]["content"][0]["text"]
        data = json.loads(content_text)
        assert data["title"] == "Adabiyot 8-sinf"


@pytest.mark.django_db
def test_sse_endpoint_authentication(auth_header):
    client = Client()

    # Tokensiz 401
    resp_unauth = client.get("/mcp/sse/")
    assert resp_unauth.status_code == 401

    # Token bilan 200 Streaming
    resp_auth = client.get("/mcp/sse/", HTTP_AUTHORIZATION=auth_header)
    assert resp_auth.status_code == 200
    assert "text/event-stream" in resp_auth["Content-Type"]


@pytest.mark.django_db
def test_messages_endpoint_jsonrpc(auth_header):
    client = Client()

    # Tokensiz 401
    resp_unauth = client.post(
        "/mcp/messages/",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        content_type="application/json",
    )
    assert resp_unauth.status_code == 401

    # Token bilan JSON-RPC ping
    resp_ping = client.post(
        "/mcp/messages/",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=auth_header,
    )
    assert resp_ping.status_code == 200
    body = resp_ping.json()
    assert body["id"] == 1
    assert body["result"] == {}


def test_openapi_spec_generation():
    client = Client()
    resp = client.get("/mcp/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["openapi"] == "3.1.0"
    assert "/tools/create_quiz_draft" in spec["paths"]
    assert "/tools/start_session" in spec["paths"]
    assert len(spec["paths"]) == 17
