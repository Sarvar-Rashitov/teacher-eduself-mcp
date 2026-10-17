from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.authentication'
    verbose_name = 'Autentifikatsiya va RBAC'

    def ready(self):
        # Kelajakda signallar yuklanishi mumkin (masalan, TeacherProfile avtomatik yaratish)
        pass
