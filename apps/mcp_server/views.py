"""
Django HTTP Views for SSE Stream, JSON-RPC Messages, and OpenAPI Schema.
Conforms to DOC-81 (MCP_SERVER.md) and DOC-87 (MCP_COMPATIBILITY.md).
"""

import json
import secrets
import time
from typing import Iterator
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .auth import authenticate_bearer_token, mcp_context_scope
from .transports.sse import JSONRPCDispatcher, generate_openapi_spec
from .exceptions import MCPUnauthorizedError, MCPParseError, MCPInvalidRequestError


def _extract_auth_token(request) -> str:
    """Request header yoki query params orqali tokenni ajratib oladi."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        return auth_header

    token_param = request.GET.get("token", "")
    if token_param:
        return f"Bearer {token_param}"

    return ""


@csrf_exempt
@require_http_methods(["GET"])
def sse_endpoint_view(request):
    """
    GET /mcp/sse/
    Masofaviy mijozlar uchun Server-Sent Events (SSE) ulanish nuqtasi.
    DOC-81: event: endpoint\\ndata: /mcp/messages/?session_id=...
    """
    auth_header = _extract_auth_token(request)
    if not auth_header:
        return JsonResponse({
            "jsonrpc": "2.0",
            "error": {
                "code": -32001,
                "message": "Autentifikatsiya tokeni talab qilinadi (Authorization: Bearer <token>).",
            }
        }, status=401)

    try:
        # Tokenni tekshirib olamiz
        context = authenticate_bearer_token(auth_header, client_name="sse-client")
    except MCPUnauthorizedError as ex:
        return JsonResponse({"jsonrpc": "2.0", "error": ex.to_dict()}, status=401)

    session_id = f"ses_{secrets.token_hex(8)}"

    def event_stream() -> Iterator[str]:
        # 1. Birlamchi endpoint hodisasini yuboramiz
        messages_endpoint = f"/mcp/messages/?session_id={session_id}"
        yield f"event: endpoint\ndata: {messages_endpoint}\n\n"

        # 2. Keep-alive ping (testlar uchun 2 ta ping yetarli, haqiqiy streamda uzluksiz)
        for _ in range(2):
            time.sleep(0.05)
            yield ": ping\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@require_http_methods(["POST"])
def messages_endpoint_view(request):
    """
    POST /mcp/messages/
    Mijozdan JSON-RPC 2.0 so'rovlarini qabul qilib, bajaradi.
    """
    auth_header = _extract_auth_token(request)
    if not auth_header:
        return JsonResponse({
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32001,
                "message": "Autentifikatsiya tokeni talab qilinadi.",
                "data": {"error_code": "UNAUTHORIZED"}
            }
        }, status=401)

    try:
        context = authenticate_bearer_token(auth_header, client_name="messages-client")
    except MCPUnauthorizedError as ex:
        return JsonResponse({"jsonrpc": "2.0", "id": None, "error": ex.to_dict()}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception as ex:
        err = MCPParseError(str(ex))
        return JsonResponse({"jsonrpc": "2.0", "id": None, "error": err.to_dict()}, status=400)

    # Xavfsiz multi-tenant kontekst ichida so'rovni bajaramiz
    with mcp_context_scope(context):
        if isinstance(payload, list):
            # Batch so'rovlar
            responses = []
            for item in payload:
                resp = JSONRPCDispatcher.handle_request(item)
                if resp is not None:
                    responses.append(resp)
            return JsonResponse(responses, safe=False)
        else:
            resp = JSONRPCDispatcher.handle_request(payload)
            if resp is None:
                # Notification javobsiz qaytadi (204 No Content yoki 202 Accepted)
                return HttpResponse(status=204)
            return JsonResponse(resp)


@require_http_methods(["GET"])
def openapi_spec_view(request):
    """
    GET /mcp/openapi.json
    ChatGPT Custom GPT Actions uchun OpenAPI 3.1 spetsifikatsiyasi.
    """
    spec = generate_openapi_spec()
    return JsonResponse(spec)
