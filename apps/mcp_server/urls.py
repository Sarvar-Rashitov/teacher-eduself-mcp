"""
URL Configuration for apps.mcp_server.
"""

from django.urls import path
from . import views

app_name = "mcp_server"

urlpatterns = [
    path("sse/", views.sse_endpoint_view, name="sse"),
    path("messages/", views.messages_endpoint_view, name="messages"),
    path("openapi.json", views.openapi_spec_view, name="openapi_spec"),
]
