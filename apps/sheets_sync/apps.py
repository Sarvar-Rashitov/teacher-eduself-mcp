"""
Django AppConfig for apps.sheets_sync.
Registers signals upon application readiness.
"""

from django.apps import AppConfig


class SheetsSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sheets_sync'
    verbose_name = 'Google Sheets Sinxronizatsiyasi'

    def ready(self):
        try:
            import apps.sheets_sync.signals  # noqa
        except ImportError:
            pass
