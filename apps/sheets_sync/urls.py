"""
URL configuration for apps.sheets_sync.
"""

from django.urls import path
from apps.sheets_sync.views import (
    ExportQuizToSheetAPIView,
    ImportSheetToQuizAPIView,
    ExportSessionResultsAPIView,
    SheetSyncStatusAPIView,
    SheetMappingsListAPIView,
)

app_name = 'sheets_sync'

urlpatterns = [
    path('export-quiz/', ExportQuizToSheetAPIView.as_view(), name='export-quiz'),
    path('import-quiz/', ImportSheetToQuizAPIView.as_view(), name='import-quiz'),
    path('export-session/', ExportSessionResultsAPIView.as_view(), name='export-session'),
    path('status/<uuid:quiz_id>/', SheetSyncStatusAPIView.as_view(), name='quiz-sync-status'),
    path('mappings/', SheetMappingsListAPIView.as_view(), name='mappings-list'),
]
