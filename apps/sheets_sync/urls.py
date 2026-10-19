# apps/sheets_sync/urls.py
from django.urls import path
from apps.sheets_sync import views

app_name = 'sheets_sync'

urlpatterns = [
    path('import/', views.SheetImportView.as_view(), name='sheet_import'),
    path('export/<uuid:quiz_id>/', views.SheetExportView.as_view(), name='sheet_export'),
    path('export-results/<uuid:session_id>/', views.SheetExportResultsView.as_view(), name='sheet_export_results'),
    path('status/<uuid:quiz_id>/', views.SheetSyncStatusView.as_view(), name='sheet_sync_status'),
]
