# ============================================================
# EduSelf Teacher — apps/mcp_server/views.py
# OAuth 2.1 PKCE Endpoints & MCP SSE / Messages HTTP Views
# MCP_SERVER.md DOC-81 va MCP_AUTH.md DOC-84 asosida
# ============================================================
import json
import uuid
from datetime import timedelta
from asgiref.sync import async_to_sync

from django.conf import settings
from django.contrib.auth import authenticate, login, get_user_model
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.mcp_server.auth import (
    authenticate_token,
    generate_access_token,
    verify_pkce,
    set_current_mcp_context,
    reset_current_mcp_context,
    DEFAULT_SCOPES,
)
from apps.mcp_server.exceptions import (
    EduSelfMCPException,
    MCPUnauthorizedError,
    MCPForbiddenError,
    MCPResourceNotFoundError,
    CODE_INVALID_PARAMS,
    CODE_METHOD_NOT_FOUND,
    CODE_PARSE_ERROR,
    CODE_INVALID_REQUEST,
)
from apps.mcp_server.models import MCPClient, MCPOAuthAuthorizationCode
from apps.mcp_server.server import mcp_server
from apps.mcp_server.transports.sse import SSESessionManager, sse_event_stream

User = get_user_model()


# ============================================================
# 1. OAuth 2.1 + PKCE Endpoints
# ============================================================
@method_decorator(csrf_exempt, name='dispatch')
class OAuthAuthorizeView(View):
    """
    GET /oauth/authorize/
    OAuth 2.1 avtorizatsiya so'rovi va kod taqdim etish.
    """
    def get(self, request):
        client_id = request.GET.get('client_id')
        redirect_uri = request.GET.get('redirect_uri')
        response_type = request.GET.get('response_type')
        code_challenge = request.GET.get('code_challenge')
        code_challenge_method = request.GET.get('code_challenge_method', 'S256')
        scope = request.GET.get('scope', " ".join(DEFAULT_SCOPES))
        state = request.GET.get('state', '')

        if not client_id or not redirect_uri:
            return JsonResponse({'error': 'invalid_request', 'error_description': 'client_id va redirect_uri majburiy'}, status=400)

        if response_type != 'code':
            return JsonResponse({'error': 'unsupported_response_type', 'error_description': 'Faqat response_type=code qo\'llab-quvvatlanadi'}, status=400)

        if not code_challenge:
            return JsonResponse({'error': 'invalid_request', 'error_description': 'PKCE code_challenge majburiy'}, status=400)

        user = request.user
        # Agar foydalanuvchi tizimga kirmagan bo'lsa (masalan test yoki API orqali auth_user parametri)
        if not user.is_authenticated:
            auth_username = request.GET.get('username')
            if auth_username:
                try:
                    user = User.objects.get(username=auth_username)
                except User.DoesNotExist:
                    pass

        if not user.is_authenticated:
            # Login sahifasiga yo'naltirish yoki oddiy xabar
            return JsonResponse({'error': 'login_required', 'error_description': 'Foydalanuvchi avval tizimga kirishi shart'}, status=401)

        # 10 daqiqa yashovchi bir martalik kod yaratamiz
        code_str = f"auth_code_{uuid.uuid4().hex}"
        MCPOAuthAuthorizationCode.objects.create(
            code=code_str,
            user=user,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scopes=scope,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        redirect_target = f"{redirect_uri}?code={code_str}"
        if state:
            redirect_target += f"&state={state}"

        return HttpResponseRedirect(redirect_target)


@method_decorator(csrf_exempt, name='dispatch')
class OAuthTokenView(View):
    """
    POST /oauth/token/
    PKCE kodini tekshirib, 1 soatlik access_token va refresh_token berish.
    """
    def post(self, request):
        grant_type = request.POST.get('grant_type') or request.GET.get('grant_type')
        client_id = request.POST.get('client_id') or request.GET.get('client_id')
        code = request.POST.get('code') or request.GET.get('code')
        redirect_uri = request.POST.get('redirect_uri') or request.GET.get('redirect_uri')
        code_verifier = request.POST.get('code_verifier') or request.GET.get('code_verifier')

        # Agar JSON body kelgan bo'lsa
        if not grant_type and request.body:
            try:
                body_data = json.loads(request.body)
                grant_type = body_data.get('grant_type')
                client_id = body_data.get('client_id')
                code = body_data.get('code')
                redirect_uri = body_data.get('redirect_uri')
                code_verifier = body_data.get('code_verifier')
            except Exception:
                pass

        if grant_type != 'authorization_code':
            return JsonResponse({'error': 'unsupported_grant_type', 'error_description': 'Faqat authorization_code qo\'llab-quvvatlanadi'}, status=400)

        if not code or not code_verifier:
            return JsonResponse({'error': 'invalid_request', 'error_description': 'code va code_verifier majburiy'}, status=400)

        try:
            auth_code = MCPOAuthAuthorizationCode.objects.select_related('user').get(code=code)
        except MCPOAuthAuthorizationCode.DoesNotExist:
            return JsonResponse({'error': 'invalid_grant', 'error_description': 'Noto\'g\'ri yoki mavjud bo\'lmagan avtorizatsiya kodi'}, status=400)

        if not auth_code.is_valid():
            return JsonResponse({'error': 'invalid_grant', 'error_description': 'Avtorizatsiya kodi eskirgan yoki foydalanilgan'}, status=400)

        # PKCE S256 tekshiruvi
        if not verify_pkce(code_verifier, auth_code.code_challenge, auth_code.code_challenge_method):
            return JsonResponse({'error': 'invalid_grant', 'error_description': 'PKCE code_verifier mos kelmadi'}, status=400)

        # Kodni ishlatilgan deb belgilaymiz
        auth_code.is_used = True
        auth_code.save(update_fields=['is_used'])

        scopes_list = [s.strip() for s in auth_code.scopes.split() if s.strip()]
        access_token = generate_access_token(
            user=auth_code.user,
            scopes=scopes_list,
            client_id=client_id,
            expires_in=3600
        )
        refresh_token = f"rfr_{uuid.uuid4().hex}"

        return JsonResponse({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": refresh_token,
            "scope": auth_code.scopes,
        })


# ============================================================
# 2. MCP HTTP SSE & JSON-RPC Messages Endpoints
# ============================================================
@method_decorator(csrf_exempt, name='dispatch')
class MCPSSEServerView(View):
    """
    GET /mcp/sse/
    SSE oqimini ochadi va mijozga xabarlar yuboriladigan endpointni e'lon qiladi.
    """
    def get(self, request):
        auth_header = request.headers.get("Authorization") or request.GET.get("token")
        if not auth_header:
            return JsonResponse({"error": "Authorization Bearer token required"}, status=401)

        try:
            ctx = authenticate_token(auth_header)
        except MCPUnauthorizedError as e:
            return JsonResponse({"error": str(e)}, status=401)

        session_id = f"ses_{uuid.uuid4().hex[:8]}"
        SSESessionManager.register(session_id, context=ctx)

        message_endpoint = f"/mcp/messages/?session_id={session_id}"
        response = StreamingHttpResponse(
            sse_event_stream(session_id, message_endpoint),
            content_type="text/event-stream"
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class MCPMessagesView(View):
    """
    POST /mcp/messages/?session_id=...
    Mijozdan kelgan JSON-RPC 2.0 so'rovlarini qabul qilib, mos tool/resurslarga yo'naltiradi.
    """
    def post(self, request):
        session_id = request.GET.get('session_id')
        ctx = None

        # 1. Kontekstni aniqlaymiz: Header yoki SSE sessiyasidan
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                ctx = authenticate_token(auth_header)
            except MCPUnauthorizedError as e:
                return JsonResponse({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32001, "message": str(e)}
                }, status=401)
        elif session_id:
            ctx = SSESessionManager.get_context(session_id)

        if not ctx:
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32001, "message": "Avtorizatsiya talab qilinadi"}
            }, status=401)

        # 2. JSON-RPC so'rovini o'qiymiz
        try:
            body = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": CODE_PARSE_ERROR, "message": "Parse Error: Yaroqsiz JSON matni"}
            }, status=400)

        req_id = body.get("id")
        method = body.get("method")
        params = body.get("params", {})

        # ContextVar o'rnatamiz
        token = set_current_mcp_context(ctx)

        try:
            result = async_to_sync(self._dispatch_method)(method, params)
            response_payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            }
            # Agar SSE sessiyasi mavjud bo'lsa, oqimga ham uzatamiz
            if session_id:
                async_to_sync(SSESessionManager.push_message)(session_id, response_payload)

            return JsonResponse(response_payload)

        except EduSelfMCPException as exc:
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "data": exc.data
                }
            }, status=200)

        except Exception as exc:
            target_exc = exc
            while hasattr(target_exc, "__cause__") and target_exc.__cause__:
                target_exc = target_exc.__cause__
            if isinstance(target_exc, EduSelfMCPException):
                return JsonResponse({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": target_exc.code,
                        "message": target_exc.message,
                        "data": target_exc.data
                    }
                }, status=200)
            return JsonResponse({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": f"Server ichki xatoligi: {str(target_exc)}"
                }
            }, status=200)

        finally:
            reset_current_mcp_context(token)

    async def _dispatch_method(self, method: str, params: dict):
        if method == "initialize":
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": True, "listChanged": False},
                    "prompts": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "eduself-teacher-mcp",
                    "version": "1.0.0"
                }
            }

        elif method == "notifications/initialized":
            return {"status": "ok"}

        elif method == "tools/list":
            tools_list = await mcp_server.list_tools()
            return {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": getattr(t, 'input_schema', None) or getattr(t, 'inputSchema', {}),
                    }
                    for t in tools_list
                ]
            }

        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            call_res = await mcp_server.call_tool(name, arguments)
            if hasattr(call_res, "structured_content") and call_res.structured_content:
                if isinstance(call_res.structured_content, dict) and "result" in call_res.structured_content:
                    return call_res.structured_content["result"]
                return call_res.structured_content
            if hasattr(call_res, "content") and call_res.content:
                return {"content": [c.text if hasattr(c, 'text') else str(c) for c in call_res.content]}
            return {"result": "success"}

        elif method == "resources/list":
            res_list = await mcp_server.list_resources()
            return {
                "resources": [
                    {
                        "uri": str(r.uri),
                        "name": r.name,
                        "description": r.description,
                        "mimeType": getattr(r, "mimeType", "application/json"),
                    }
                    for r in res_list
                ]
            }

        elif method == "resources/read":
            uri = params.get("uri")
            contents = await mcp_server.read_resource(uri)
            return {"contents": contents}

        elif method == "prompts/list":
            prompt_list = await mcp_server.list_prompts()
            return {
                "prompts": [
                    {
                        "name": p.name,
                        "description": p.description,
                        "arguments": [
                            {"name": a.name, "description": a.description, "required": a.required}
                            for a in getattr(p, "arguments", [])
                        ]
                    }
                    for p in prompt_list
                ]
            }

        elif method == "prompts/get":
            name = params.get("name")
            arguments = params.get("arguments", {})
            prompt_res = await mcp_server.get_prompt(name, arguments)
            return {"description": prompt_res.description, "messages": prompt_res.messages}

        else:
            raise EduSelfMCPException(
                code=CODE_METHOD_NOT_FOUND,
                message=f"Metod topilmadi: '{method}'"
            )
