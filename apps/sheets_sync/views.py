"""
REST API Views for Google Sheets Synchronization (Phase 09).
Provides endpoints to trigger exports, imports, gradebook generation, and monitor logs.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.sheets_sync.models import SheetMapping, SheetSyncLog
from apps.sheets_sync.tasks import (
    sync_quiz_to_sheet_task,
    import_sheet_to_quiz_task,
    export_session_results_task,
)
from apps.sheets_sync.services import export_quiz_to_sheet, import_sheet_to_quiz


def _parse_bool(val, default=True):
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.lower() not in ('false', '0', 'no', 'f', 'off')
    return bool(val)


class ExportQuizToSheetAPIView(APIView):
    """
    POST /api/v1/sheets/export-quiz/
    Triggers export of Quiz questions to a Google Sheet.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quiz_id = request.data.get('quiz_id')
        spreadsheet_url = request.data.get('spreadsheet_url')
        is_async = _parse_bool(request.data.get('async', True), default=True)

        if not quiz_id or not spreadsheet_url:
            return Response(
                {'success': False, 'error': 'quiz_id va spreadsheet_url parametrlari talab qilinadi.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quiz = Quiz.objects.get(id=quiz_id, owner=request.user)
        except Quiz.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Viktorina topilmadi yoki sizda unga ruxsat yo‘q.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if is_async:
            task = sync_quiz_to_sheet_task.delay(str(quiz.id), spreadsheet_url, request.user.id)
            return Response({
                'success': True,
                'message': 'Eksport fon rejimida boshlandi.',
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
        else:
            log = export_quiz_to_sheet(quiz=quiz, spreadsheet_url=spreadsheet_url)
            return Response({
                'success': True,
                'message': 'Eksport muvaffaqiyatli yakunlandi.',
                'log_id': str(log.id),
                'rows_processed': log.rows_processed,
                'duration_ms': log.duration_ms
            }, status=status.HTTP_200_OK)


class ImportSheetToQuizAPIView(APIView):
    """
    POST /api/v1/sheets/import-quiz/
    Triggers import of questions from Google Sheet into a Quiz.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quiz_id = request.data.get('quiz_id')
        spreadsheet_url = request.data.get('spreadsheet_url')
        overwrite = _parse_bool(request.data.get('overwrite', True), default=True)
        is_async = _parse_bool(request.data.get('async', True), default=True)

        if not quiz_id or not spreadsheet_url:
            return Response(
                {'success': False, 'error': 'quiz_id va spreadsheet_url parametrlari talab qilinadi.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quiz = Quiz.objects.get(id=quiz_id, owner=request.user)
        except Quiz.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Viktorina topilmadi yoki sizda unga ruxsat yo‘q.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if is_async:
            task = import_sheet_to_quiz_task.delay(str(quiz.id), spreadsheet_url, request.user.id, overwrite)
            return Response({
                'success': True,
                'message': 'Import fon rejimida boshlandi.',
                'task_id': task.id
            }, status=status.HTTP_202_ACCEPTED)
        else:
            log = import_sheet_to_quiz(quiz=quiz, spreadsheet_url=spreadsheet_url, overwrite_unlocked=overwrite)
            return Response({
                'success': True,
                'message': 'Import muvaffaqiyatli yakunlandi.',
                'log_id': str(log.id),
                'rows_processed': log.rows_processed,
                'duration_ms': log.duration_ms
            }, status=status.HTTP_200_OK)


class ExportSessionResultsAPIView(APIView):
    """
    POST /api/v1/sheets/export-session/
    Manually triggers gradebook export for a completed session.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        spreadsheet_url = request.data.get('spreadsheet_url')

        if not session_id:
            return Response(
                {'success': False, 'error': 'session_id parametri talab qilinadi.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = LiveSession.objects.get(id=session_id, host=request.user)
        except LiveSession.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Sessiya topilmadi yoki sizda unga ruxsat yo‘q.'},
                status=status.HTTP_404_NOT_FOUND
            )

        task = export_session_results_task.delay(str(session.id), spreadsheet_url)
        return Response({
            'success': True,
            'message': 'Sessiya natijalarini eksport qilish boshlandi.',
            'task_id': task.id
        }, status=status.HTTP_202_ACCEPTED)


class SheetSyncStatusAPIView(APIView):
    """
    GET /api/v1/sheets/status/<uuid:quiz_id>/
    Returns mapping status and recent audit logs for a Quiz.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, quiz_id):
        try:
            quiz = Quiz.objects.get(id=quiz_id, owner=request.user)
        except Quiz.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Viktorina topilmadi.'},
                status=status.HTTP_404_NOT_FOUND
            )

        mapping = quiz.sheet_mappings.filter(is_active=True).first()
        logs = SheetSyncLog.objects.filter(quiz=quiz).order_by('-created_at')[:10]

        logs_data = [{
            'id': str(l.id),
            'sync_type': l.sync_type,
            'status': l.status,
            'rows_processed': l.rows_processed,
            'duration_ms': l.duration_ms,
            'error_details': l.error_details,
            'created_at': l.created_at.isoformat()
        } for l in logs]

        return Response({
            'success': True,
            'quiz_id': str(quiz.id),
            'quiz_title': quiz.title,
            'google_sheet_url': quiz.google_sheet_url,
            'mapping': {
                'spreadsheet_id': mapping.spreadsheet_id,
                'spreadsheet_url': mapping.spreadsheet_url,
                'sheet_name': mapping.sheet_name,
                'sync_status': mapping.sync_status,
                'last_synced_at': mapping.last_synced_at.isoformat() if mapping.last_synced_at else None,
                'last_error': mapping.last_error,
            } if mapping else None,
            'recent_logs': logs_data
        }, status=status.HTTP_200_OK)


class SheetMappingsListAPIView(APIView):
    """
    GET /api/v1/sheets/mappings/
    Returns all sheet mappings belonging to the current teacher.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mappings = SheetMapping.objects.filter(teacher=request.user, is_active=True).select_related('quiz')
        data = [{
            'id': str(m.id),
            'quiz_id': str(m.quiz.id),
            'quiz_title': m.quiz.title,
            'spreadsheet_id': m.spreadsheet_id,
            'spreadsheet_url': m.spreadsheet_url,
            'sheet_name': m.sheet_name,
            'sync_direction': m.sync_direction,
            'sync_status': m.sync_status,
            'auto_sync_on_session_end': m.auto_sync_on_session_end,
            'last_synced_at': m.last_synced_at.isoformat() if m.last_synced_at else None,
        } for m in mappings]

        return Response({'success': True, 'mappings': data}, status=status.HTTP_200_OK)
