from django.apps import AppConfig


class MCPServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mcp_server"
    label = "mcp_server"
    verbose_name = "Model Context Protocol (MCP) Server"
