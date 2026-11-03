"""
Django Admin registration for apps.sheets_sync.
Provides clear status indicators, filtering, and audit inspection.
"""

from django.contrib import admin
from apps.sheets_sync.models import SheetMapping, SheetSyncLog


@admin.register(SheetMapping)
class SheetMappingAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'teacher', 'sheet_name', 'sync_direction', 'sync_status', 'last_synced_at', 'is_active')
    list_filter = ('sync_status', 'sync_direction', 'is_active', 'auto_sync_on_session_end')
    search_fields = ('quiz__title', 'teacher__username', 'teacher__first_name', 'teacher__last_name', 'spreadsheet_id', 'sheet_name')
    readonly_fields = ('created_at', 'updated_at', 'last_synced_at')


@admin.register(SheetSyncLog)
class SheetSyncLogAdmin(admin.ModelAdmin):
    list_display = ('sync_type', 'status', 'quiz', 'session', 'rows_processed', 'duration_ms', 'created_at')
    list_filter = ('sync_type', 'status', 'created_at')
    search_fields = ('quiz__title', 'session__room_code', 'error_details')
    readonly_fields = ('created_at',)
