"""
Celery Background Tasks for Google Sheets Synchronization.
Handles asynchronous exports, imports, gradebook generation, and periodic polling.
"""

import logging
from typing import Optional, Dict, Any
from celery import shared_task
from django.contrib.auth import get_user_model


from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.sheets_sync.models import SheetMapping
from apps.sheets_sync.services import (
    export_quiz_to_sheet,
    import_sheet_to_quiz,
    export_session_results_to_sheet,
)

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def sync_quiz_to_sheet_task(self, quiz_id: str, spreadsheet_url: str, teacher_id: Optional[int] = None):
    """
    Asynchronous Celery task to export Quiz questions to Google Sheet.
    Retries up to 3 times on transient network/API issues.
    """
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        log = export_quiz_to_sheet(quiz=quiz, spreadsheet_url=spreadsheet_url)
        logger.info(f"Quiz {quiz.title} successfully exported to sheet {spreadsheet_url} in {log.duration_ms}ms")
        return {
            'status': 'success',
            'log_id': str(log.id),
            'rows_processed': log.rows_processed,
            'duration_ms': log.duration_ms
        }
    except Exception as exc:
        logger.error(f"Error exporting quiz {quiz_id} to sheet: {exc}", exc_info=True)
        # Update mapping status if exists
        SheetMapping.objects.filter(quiz_id=quiz_id, spreadsheet_url=spreadsheet_url).update(
            sync_status='failed',
            last_error=str(exc)
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def import_sheet_to_quiz_task(self, quiz_id: str, spreadsheet_url: str, teacher_id: Optional[int] = None, overwrite: bool = True):
    """
    Asynchronous Celery task to import questions from Google Sheet into a Quiz.
    Protects locked questions (is_locked=True).
    """
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        log = import_sheet_to_quiz(quiz=quiz, spreadsheet_url=spreadsheet_url, overwrite_unlocked=overwrite)
        logger.info(f"Questions imported into Quiz {quiz.title} from sheet {spreadsheet_url} ({log.rows_processed} rows)")
        return {
            'status': 'success',
            'log_id': str(log.id),
            'rows_processed': log.rows_processed,
            'duration_ms': log.duration_ms
        }
    except Exception as exc:
        logger.error(f"Error importing sheet to quiz {quiz_id}: {exc}", exc_info=True)
        SheetMapping.objects.filter(quiz_id=quiz_id, spreadsheet_url=spreadsheet_url).update(
            sync_status='failed',
            last_error=str(exc)
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def export_session_results_task(self, session_id: str, spreadsheet_url: Optional[str] = None):
    """
    Asynchronous Celery task to write live session final scores into the linked Google Sheet.
    Executed automatically when session.status becomes 'completed'.
    """
    try:
        session = LiveSession.objects.select_related('quiz').get(id=session_id)
        log = export_session_results_to_sheet(session=session, spreadsheet_url=spreadsheet_url)
        logger.info(f"Session {session.room_code} results exported to sheet ({log.rows_processed} students)")
        return {
            'status': 'success',
            'log_id': str(log.id),
            'rows_processed': log.rows_processed,
            'duration_ms': log.duration_ms
        }
    except Exception as exc:
        logger.error(f"Error exporting session {session_id} results to sheet: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task
def poll_sheet_changes_periodic_task():
    """
    Periodic task (scheduled via Celery Beat) to poll active sheet mappings
    and sync any changes made directly in Google Sheets by teachers.
    """
    active_mappings = SheetMapping.objects.filter(
        is_active=True,
        sync_direction__in=['bidirectional', 'import_only']
    )
    synced_count = 0
    errors_count = 0

    for mapping in active_mappings:
        try:
            import_sheet_to_quiz(quiz=mapping.quiz, spreadsheet_url=mapping.spreadsheet_url, sheet_name=mapping.sheet_name)
            synced_count += 1
        except Exception as exc:
            errors_count += 1
            logger.warning(f"Periodic poll failed for mapping {mapping.id}: {exc}")

    return {
        'total_mappings': active_mappings.count(),
        'synced_count': synced_count,
        'errors_count': errors_count
    }
