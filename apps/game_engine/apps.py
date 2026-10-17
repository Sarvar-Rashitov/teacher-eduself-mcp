from django.apps import AppConfig


class GameEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.game_engine'
    verbose_name = 'O‘yin Rejimlari va Dvigateli'

    def ready(self):
        # O'yin rejimlari plaginlarini avtomatik ro'yxatga olish
        try:
            import apps.game_engine.modes  # noqa: F401
        except ImportError:
            pass
