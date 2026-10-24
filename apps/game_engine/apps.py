from django.apps import AppConfig


class GameEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.game_engine"
    label = "game_engine"
    verbose_name = "EduSelf Game Engine"

    def ready(self):
        # Auto-discover and register game modes
        try:
            import apps.game_engine.modes  # noqa: F401
        except ImportError:
            pass
