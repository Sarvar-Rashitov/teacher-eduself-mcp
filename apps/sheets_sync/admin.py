"""
Django Admin registration for Google Sheets Synchronization models.
"""

from django.contrib import admin
from apps.sheets_sync.models import SheetMapping, SheetSyncLog


@admin.register(SheetMapping)
class SheetMappingAdmin(admin.ModelAdmin):
    list_display = (
        "quiz",
        "spreadsheet_id",
        "sheet_name",
        "sync_mode",
        "auto_sync",
        "last_synced_at",
        "updated_at",
    )
    list_filter = ("sync_mode", "auto_sync", "created_at")
    search_fields = ("quiz__title", "spreadsheet_id", "spreadsheet_url")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(SheetSyncLog)
class SheetSyncLogAdmin(admin.ModelAdmin):
    list_display = (
        "quiz",
        "direction",
        "status",
        "rows_processed",
        "created_at",
    )
    list_filter = ("direction", "status", "created_at")
    search_fields = ("quiz__title", "error_message")
    readonly_fields = ("id", "created_at")
