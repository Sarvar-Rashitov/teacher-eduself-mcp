# apps/sheets_sync/views.py
"""
Google Sheets REST API Views.
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
    sync_quiz_from_sheet_task,
    export_quiz_to_sheet_task,
    export_session_results_task,
)


class SheetImportView(APIView):
    """Google Sheet jadvalidan savollarni import qilish."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sheet_url = request.data.get('sheet_url')
        quiz_id = request.data.get('quiz_id')
        is_async = request.data.get('async', True)

        if not sheet_url or not quiz_id:
            return Response(
                {'success': False, 'error': {'code': 'INVALID_PARAMS', 'message': "sheet_url va quiz_id talab qilinadi."}},
                status=status.HTTP_400_BAD_REQUEST
            )

        quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)

        if is_async:
            task = sync_quiz_from_sheet_task.delay(str(quiz.id), sheet_url)
            return Response({
                'success': True,
                'task_id': task.id,
                'message': "Import jarayoni fonga (Celery) topshirildi."
            }, status=status.HTTP_202_ACCEPTED)

        try:
            service = GoogleSheetsSyncService()
            count, log = service.import_questions_from_sheet(sheet_url, quiz)
            return Response({
                'success': True,
                'questions_created': count,
                'duration_ms': log.duration_ms
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': {'code': 'SYNC_ERROR', 'message': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)


class SheetExportView(APIView):
    """Viktorina savollarini Google Sheet jadvaliga eksport qilish."""
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        sheet_url = request.data.get('sheet_url')
        if not sheet_url:
            return Response(
                {'success': False, 'error': {'code': 'INVALID_PARAMS', 'message': "sheet_url talab qilinadi."}},
                status=status.HTTP_400_BAD_REQUEST
            )

        quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)
        is_async = request.data.get('async', True)

        if is_async:
            task = export_quiz_to_sheet_task.delay(str(quiz.id), sheet_url)
            return Response({
                'success': True,
                'task_id': task.id,
                'message': "Eksport jarayoni fonga (Celery) topshirildi."
            }, status=status.HTTP_202_ACCEPTED)

        try:
            service = GoogleSheetsSyncService()
            count, log = service.export_quiz_to_sheet(quiz, sheet_url)
            return Response({
                'success': True,
                'questions_exported': count,
                'duration_ms': log.duration_ms
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'error': {'code': 'EXPORT_ERROR', 'message': str(e)}
            }, status=status.HTTP_400_BAD_REQUEST)


class SheetExportResultsView(APIView):
    """Jonli dars natijalarini Google Sheet jadvaliga eksport qilish."""
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        sheet_url = request.data.get('sheet_url')
        if not sheet_url:
            return Response(
                {'success': False, 'error': {'code': 'INVALID_PARAMS', 'message': "sheet_url talab qilinadi."}},
                status=status.HTTP_400_BAD_REQUEST
            )

        session = get_object_or_404(LiveSession, id=session_id, host=request.user)
        task = export_session_results_task.delay(str(session.id), sheet_url)
        return Response({
            'success': True,
            'task_id': task.id,
            'message': "Natijalarni eksport qilish fonga (Celery) topshirildi."
        }, status=status.HTTP_202_ACCEPTED)


class SheetSyncStatusView(APIView):
    """Viktorina bo'yicha so'nggi sinxronizatsiya holati va loglari."""
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)
        mapping = SheetMapping.objects.filter(quiz=quiz, is_active=True).first()
        logs = SheetSyncLog.objects.filter(quiz=quiz).order_by('-created_at')[:10]

        return Response({
            'success': True,
            'quiz_id': str(quiz.id),
            'sheet_url': mapping.sheet_url if mapping else None,
            'last_synced_at': mapping.last_synced_at if mapping else None,
            'sync_direction': mapping.sync_direction if mapping else None,
            'recent_logs': [
                {
                    'id': str(l.id),
                    'direction': l.direction,
                    'status': l.status,
                    'rows_processed': l.rows_processed,
                    'duration_ms': l.duration_ms,
                    'error_message': l.error_message,
                    'created_at': l.created_at
                }
                for l in logs
            ]
        })
