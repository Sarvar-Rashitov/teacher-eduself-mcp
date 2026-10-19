# apps/sheets_sync/admin.py
from django.contrib import admin
from apps.sheets_sync.models import SheetMapping, SheetSyncLog


@admin.register(SheetMapping)
class SheetMappingAdmin(admin.ModelAdmin):
    list_display = ('id', 'quiz', 'session', 'sheet_url', 'sync_direction', 'last_synced_at', 'is_active')
    list_filter = ('sync_direction', 'is_active', 'created_at')
    search_fields = ('sheet_url', 'spreadsheet_id', 'quiz__title', 'session__room_code')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(SheetSyncLog)
class SheetSyncLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'quiz', 'session', 'direction', 'status', 'rows_processed', 'duration_ms', 'created_at')
    list_filter = ('direction', 'status', 'created_at')
    search_fields = ('quiz__title', 'session__room_code', 'error_message')
    readonly_fields = ('id', 'created_at')
