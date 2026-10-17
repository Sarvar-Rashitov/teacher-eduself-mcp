# ============================================================
# EduSelf Teacher — apps/mcp_server/urls.py
# MCP Server URL Routes
# ============================================================
from django.urls import path
from apps.mcp_server.views import (
    MCPSSEServerView,
    MCPMessagesView,
    OAuthAuthorizeView,
    OAuthTokenView,
)

app_name = 'mcp_server'

urlpatterns = [
    # SSE Transport: GET /mcp/sse/
    path('sse/', MCPSSEServerView.as_view(), name='sse'),
    path('sse', MCPSSEServerView.as_view(), name='sse_no_slash'),

    # JSON-RPC Messages: POST /mcp/messages/?session_id=...
    path('messages/', MCPMessagesView.as_view(), name='messages'),
    path('messages', MCPMessagesView.as_view(), name='messages_no_slash'),

    # Ichki OAuth marshrutlari (/mcp/oauth/...)
    path('oauth/authorize/', OAuthAuthorizeView.as_view(), name='oauth_authorize'),
    path('oauth/token/', OAuthTokenView.as_view(), name='oauth_token'),
]
