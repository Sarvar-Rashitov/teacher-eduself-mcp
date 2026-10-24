from django.apps import AppConfig


class GameEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "game_engine"
    verbose_name = "EduSelf Game Engine"

    def ready(self):
        # Auto-discover built-in game modes so they register with GameModeRegistry
        try:
            import game_engine.modes  # noqa: F401
        except ImportError:
            pass
