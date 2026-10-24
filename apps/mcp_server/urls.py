"""
URL configuration for apps.mcp_server.
Provides /mcp/sse and /mcp/messages endpoints according to DOC-81.
"""

from django.urls import path
from apps.mcp_server.transports.sse import sse_connect_view, messages_view

app_name = "mcp_server"

urlpatterns = [
    path("sse", sse_connect_view, name="sse_connect"),
    path("messages", messages_view, name="messages"),
]
