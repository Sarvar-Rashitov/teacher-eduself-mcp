from django.apps import AppConfig


class QuestionsRegistryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.questions_registry'
    verbose_name = 'Savollar Turlari Registri'

    def ready(self):
        # Automatically import types to register plugins in question_type_registry
        import apps.questions_registry.types  # noqa: F401
