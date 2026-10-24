from django.apps import AppConfig


class QuestionsRegistryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.questions_registry"
    label = "questions_registry"
    verbose_name = "Savollar Registri"

    def ready(self):
        # Savol turlarini ro'yxatga olish
        import apps.questions_registry.types
