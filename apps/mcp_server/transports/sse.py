"""
MCP Server-Sent Events (SSE) Transport according to DOC-81 (MCP_SERVER.md).
Provides HTTP SSE connection endpoint and JSON-RPC 2.0 message handler.
"""

import json
import uuid
import time
from typing import Any, Dict, Generator, Optional
from django.http import HttpResponse, StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from apps.mcp_server.auth import authenticate_header, verify_mcp_token, MCPAuthContextManager
from apps.mcp_server.exceptions import (
    MCPError,
    MCPUnauthorizedError,
    JSONRPCParseError,
    JSONRPCInvalidRequestError,
    JSONRPCMethodNotFoundError,
)
from apps.mcp_server.server import TOOL_REGISTRY, dispatch_tool, mcp_server


def _extract_token_and_auth(request) -> Any:
    """Request dan token ajratib olib autentifikatsiya qilish."""
    auth_header = request.headers.get("Authorization")
    if auth_header:
        return authenticate_header(auth_header)

    # Agar Authorization header bo'lmasa, query param dan qidirish
    token_param = request.GET.get("token")
    if token_param:
        return verify_mcp_token(token_param)

    raise MCPUnauthorizedError("Autentifikatsiya tokeni topilmadi (Bearer token talab qilinadi).")


def sse_event_stream(session_id: str, endpoint_url: str) -> Generator[str, None, None]:
    """
    SSE oqimi: birinchi bo'lib endpoint manzilini yuboradi,
    so'ngra keep-alive ping uzatadi.
    """
    # 1. Endpoint hodisasini yuborish
    yield f"event: endpoint\ndata: {endpoint_url}\n\n"

    # 2. Keep-alive uzatish (15 soniyada 1 marta ping)
    for _ in range(3):
        time.sleep(1)
        yield ": ping\n\n"


@csrf_exempt
@require_http_methods(["GET"])
def sse_connect_view(request):
    """
    GET /mcp/sse
    Masofaviy mijozlar uchun SSE oqimini ochish.
    """
    try:
        ctx = _extract_token_and_auth(request)
    except MCPError as e:
        return JsonResponse({"error": e.to_dict()}, status=401)

    session_id = f"ses_{uuid.uuid4().hex[:12]}"
    endpoint_url = f"/mcp/messages?session_id={session_id}"

    response = StreamingHttpResponse(
        sse_event_stream(session_id, endpoint_url),
        content_type="text/event-stream; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@require_http_methods(["POST"])
def messages_view(request):
    """
    POST /mcp/messages
    JSON-RPC 2.0 xabarlarini qabul qilish va asboblarni bajarish.
    """
    try:
        ctx = _extract_token_and_auth(request)
    except MCPError as e:
        return JsonResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": e.to_dict(),
        }, status=401)

    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": JSONRPCParseError().to_dict(),
        }, status=400)

    if not isinstance(body, dict):
        return JsonResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": JSONRPCInvalidRequestError().to_dict(),
        }, status=400)

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    # Kontekst bilan JSON-RPC dispetcheri
    with MCPAuthContextManager(user=ctx.user, scopes=list(ctx.scopes), client_info=ctx.client_info):
        try:
            result = _handle_jsonrpc_method(method, params, ctx)
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            })
        except MCPError as me:
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": me.to_dict(),
            }, status=200)
        except Exception as ex:
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Server ichki xatoligi: {str(ex)}",
                },
            }, status=200)


def _handle_jsonrpc_method(method: Optional[str], params: Dict[str, Any], ctx: Any) -> Any:
    """JSON-RPC metodlarini qayta ishlash."""
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": True, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": "eduself-teacher-mcp",
                "version": "1.0.0",
            },
        }

    elif method == "notifications/initialized":
        return {}

    elif method == "ping":
        return {}

    elif method in ("tools/list", "list_tools"):
        tools_list = []
        for name, func in TOOL_REGISTRY.items():
            req_scopes = getattr(func, "_required_scopes", [])
            is_destr = getattr(func, "_is_destructive", False)
            tools_list.append({
                "name": name,
                "description": (func.__doc__ or "").strip(),
                "required_scopes": req_scopes,
                "annotations": {
                    "destructiveHint": is_destr,
                    "readOnlyHint": not is_destr and "write" not in " ".join(req_scopes),
                },
            })
        return {"tools": tools_list}

    elif method in ("tools/call", "call_tool"):
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if not tool_name:
            raise JSONRPCInvalidRequestError("Tool name ko'rsatilishi shart.")

        res = dispatch_tool(tool_name, arguments, user=ctx.user, scopes=list(ctx.scopes))
        return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "structured": res}

    elif method in ("resources/list", "list_resources"):
        return {
            "resources": [
                {
                    "uri": "eduself://question-types",
                    "name": "Canonical Question Types",
                    "mimeType": "application/json",
                },
                {
                    "uri": "eduself://game-modes",
                    "name": "Available Game Modes",
                    "mimeType": "application/json",
                },
                {
                    "uri": "eduself://teacher-guide",
                    "name": "Pedagogical Teacher Guide",
                    "mimeType": "text/markdown",
                },
            ]
        }

    elif method in ("prompts/list", "list_prompts"):
        return {
            "prompts": [
                {
                    "name": "create-lesson-quiz",
                    "description": "Dars mavzusi bo'yicha viktorina yaratish",
                    "arguments": [
                        {"name": "subject", "required": True},
                        {"name": "grade", "required": True},
                        {"name": "topic", "required": False},
                    ],
                },
                {
                    "name": "analyze-session-report",
                    "description": "Sessiya natijalarini pedagogik tahlil qilish",
                    "arguments": [
                        {"name": "session_id", "required": True},
                    ],
                },
                {
                    "name": "plan-team-activity",
                    "description": "Jamoaviy o'yin rejalashtirish",
                    "arguments": [
                        {"name": "student_count", "required": True},
                        {"name": "duration_minutes", "required": True},
                    ],
                },
            ]
        }

    else:
        # To'g'ridan-to'g'ri tool chaqiruvi (masalan method="create_quiz_draft")
        if method in TOOL_REGISTRY:
            res = dispatch_tool(method, params, user=ctx.user, scopes=list(ctx.scopes))
            return res
        raise JSONRPCMethodNotFoundError(f"Noma'lum metod yoki tool: '{method}'")
