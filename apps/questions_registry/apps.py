from django.apps import AppConfig


class QuestionsRegistryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.questions_registry'
    verbose_name = 'Savollar Registri va Plaginlari'

    def ready(self):
        # Savol turlarini avtomatik ro'yxatdan o'tkazish
        from . import types  # noqa: F401
