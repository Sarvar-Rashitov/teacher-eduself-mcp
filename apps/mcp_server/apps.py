from django.apps import AppConfig


class McpServerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mcp_server'
    verbose_name = 'EduSelf MCP Server'

    def ready(self):
        # Server va barcha toollarni import qilib ro'yxatdan o'tkazamiz
        try:
            from . import server  # noqa: F401
        except Exception:
            pass
