from django.apps import AppConfig


class QuizzesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "quizzes"
    verbose_name = "Quizzes and Questions"

    def ready(self):
        # Auto-import question registry types so plugins are ready
        try:
            import questions_registry.types  # noqa: F401
        except ImportError:
            pass
