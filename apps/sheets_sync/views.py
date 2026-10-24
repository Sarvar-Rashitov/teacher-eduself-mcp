"""
REST API views for Google Sheets synchronization.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.sheets_sync.models import SheetMapping, SheetSyncLog
from apps.sheets_sync.services import GoogleSheetsSyncService
from apps.sheets_sync.tasks import (
    export_quiz_to_sheet_task,
    import_sheet_to_quiz_task,
    sync_live_session_results_task,
)


class ExportQuizToSheetView(APIView):
    """
    Viktorinani Google Sheets ga eksport qilish so'rovi.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quiz_id = request.data.get("quiz_id")
        spreadsheet_url = request.data.get("spreadsheet_url")
        worksheet_name = request.data.get("worksheet_name", "Sheet1")
        async_mode = request.data.get("async", True)

        if not quiz_id or not spreadsheet_url:
            return Response(
                {"error": "quiz_id va spreadsheet_url majburiy maydonlar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)

        if async_mode:
            task = export_quiz_to_sheet_task.delay(
                str(quiz.id),
                spreadsheet_url,
                worksheet_name,
            )
            return Response(
                {
                    "message": "Eksport vazifasi navbatga qo'shildi.",
                    "task_id": task.id,
                    "quiz_id": str(quiz.id),
                },
                status=status.HTTP_202_ACCEPTED,
            )
        else:
            try:
                service = GoogleSheetsSyncService()
                rows = service.export_quiz_to_sheet(quiz, spreadsheet_url, worksheet_name)
                return Response(
                    {"message": "Eksport muvaffaqiyatli bajarildi.", "rows_exported": rows},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ImportSheetToQuizView(APIView):
    """
    Google Sheets dan savollarni viktorinaga import qilish so'rovi.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quiz_id = request.data.get("quiz_id")
        spreadsheet_url = request.data.get("spreadsheet_url")
        worksheet_name = request.data.get("worksheet_name", "Sheet1")
        async_mode = request.data.get("async", True)

        if not quiz_id or not spreadsheet_url:
            return Response(
                {"error": "quiz_id va spreadsheet_url majburiy maydonlar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)

        if async_mode:
            task = import_sheet_to_quiz_task.delay(
                str(quiz.id),
                spreadsheet_url,
                worksheet_name,
            )
            return Response(
                {
                    "message": "Import vazifasi navbatga qo'shildi.",
                    "task_id": task.id,
                    "quiz_id": str(quiz.id),
                },
                status=status.HTTP_202_ACCEPTED,
            )
        else:
            try:
                service = GoogleSheetsSyncService()
                count = service.import_sheet_to_quiz(quiz, spreadsheet_url, worksheet_name)
                return Response(
                    {"message": "Import muvaffaqiyatli bajarildi.", "questions_imported": count},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SyncLiveSessionResultsView(APIView):
    """
    Jonli dars natijalarini Google Sheets ga eksport qilish.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        spreadsheet_url = request.data.get("spreadsheet_url")
        worksheet_name = request.data.get("worksheet_name")

        if not session_id or not spreadsheet_url:
            return Response(
                {"error": "session_id va spreadsheet_url majburiy maydonlar."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = get_object_or_404(LiveSession, id=session_id, host=request.user)

        task = sync_live_session_results_task.delay(
            str(session.id),
            spreadsheet_url,
            worksheet_name,
        )
        return Response(
            {
                "message": "Natijalarni eksport qilish vazifasi navbatga qo'shildi.",
                "task_id": task.id,
                "session_id": str(session.id),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class SheetSyncStatusView(APIView):
    """
    Viktorinaning Google Sheets bilan sinxronlash holati va jurnallari.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)
        mapping = SheetMapping.objects.filter(quiz=quiz).first()
        logs = SheetSyncLog.objects.filter(quiz=quiz).order_by("-created_at")[:10]

        mapping_data = None
        if mapping:
            mapping_data = {
                "id": str(mapping.id),
                "spreadsheet_id": mapping.spreadsheet_id,
                "spreadsheet_url": mapping.spreadsheet_url,
                "sheet_name": mapping.sheet_name,
                "sync_mode": mapping.sync_mode,
                "auto_sync": mapping.auto_sync,
                "last_synced_at": mapping.last_synced_at.isoformat() if mapping.last_synced_at else None,
            }

        logs_data = [
            {
                "id": str(log.id),
                "direction": log.direction,
                "status": log.status,
                "rows_processed": log.rows_processed,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]

        return Response(
            {
                "quiz_id": str(quiz.id),
                "mapping": mapping_data,
                "recent_logs": logs_data,
            },
            status=status.HTTP_200_OK,
        )
