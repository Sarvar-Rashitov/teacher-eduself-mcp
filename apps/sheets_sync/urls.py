"""
URLs for Google Sheets Synchronization API.
"""

from django.urls import path
from apps.sheets_sync.views import (
    ExportQuizToSheetView,
    ImportSheetToQuizView,
    SyncLiveSessionResultsView,
    SheetSyncStatusView,
)

app_name = "sheets_sync"

urlpatterns = [
    path("export/", ExportQuizToSheetView.as_view(), name="export_quiz"),
    path("import/", ImportSheetToQuizView.as_view(), name="import_sheet"),
    path("sync-session/", SyncLiveSessionResultsView.as_view(), name="sync_session"),
    path("status/<uuid:quiz_id>/", SheetSyncStatusView.as_view(), name="sync_status"),
]
