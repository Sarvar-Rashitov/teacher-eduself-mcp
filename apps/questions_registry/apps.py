from django.apps import AppConfig


class QuestionsRegistryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "questions_registry"
    verbose_name = "Questions Registry"

    def ready(self):
        # Auto-import question types to ensure they are registered
        try:
            import questions_registry.types  # noqa: F401
        except ImportError:
            pass
