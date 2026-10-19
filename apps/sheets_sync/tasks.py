# apps/sheets_sync/tasks.py
"""
Celery Background Tasks for Google Sheets Synchronization.
Backend.md §6 ('sync_sheets' navbati) va TECH_STACK.md §6-§7 asosida.
"""
import logging
from celery import shared_task
from django.utils import timezone
from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.sheets_sync.models import SheetMapping
from apps.sheets_sync.services import GoogleSheetsSyncService

logger = logging.getLogger(__name__)


@shared_task(
    queue='sync_sheets',
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='apps.sheets_sync.tasks.sync_quiz_from_sheet_task'
)
def sync_quiz_from_sheet_task(self, quiz_id: str, sheet_url: str, worksheet_title: str = None):
    """
    Google Sheet jadvalidan savollarni asinxron yuklash Celery vazifasi.
    """
    logger.info(f"Celery task boshlandi: sync_quiz_from_sheet (quiz_id={quiz_id})")
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        service = GoogleSheetsSyncService()
        created_count, log = service.import_questions_from_sheet(
            sheet_url=sheet_url,
            quiz=quiz,
            worksheet_title=worksheet_title
        )
        return {
            'status': 'success',
            'quiz_id': str(quiz_id),
            'questions_created': created_count,
            'duration_ms': log.duration_ms
        }
    except Exception as exc:
        logger.error(f"sync_quiz_from_sheet_task xatosi: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    queue='sync_sheets',
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='apps.sheets_sync.tasks.export_quiz_to_sheet_task'
)
def export_quiz_to_sheet_task(self, quiz_id: str, sheet_url: str, worksheet_title: str = "Savollar"):
    """
    Viktorina savollarini Google Sheet jadvaliga eksport qilish vazifasi.
    """
    logger.info(f"Celery task boshlandi: export_quiz_to_sheet (quiz_id={quiz_id})")
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        service = GoogleSheetsSyncService()
        exported_count, log = service.export_quiz_to_sheet(
            quiz=quiz,
            sheet_url=sheet_url,
            worksheet_title=worksheet_title
        )
        return {
            'status': 'success',
            'quiz_id': str(quiz_id),
            'questions_exported': exported_count,
            'duration_ms': log.duration_ms
        }
    except Exception as exc:
        logger.error(f"export_quiz_to_sheet_task xatosi: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    queue='sync_sheets',
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='apps.sheets_sync.tasks.export_session_results_task'
)
def export_session_results_task(self, session_id: str, sheet_url: str, worksheet_title: str = None):
    """
    Dars yakunida o'quvchilar natijalarini Google Sheet'ga yozish vazifasi.
    """
    logger.info(f"Celery task boshlandi: export_session_results (session_id={session_id})")
    try:
        session = LiveSession.objects.get(id=session_id)
        service = GoogleSheetsSyncService()
        rows_count, log = service.export_session_results_batch(
            session=session,
            sheet_url=sheet_url,
            worksheet_title=worksheet_title
        )
        return {
            'status': 'success',
            'session_id': str(session_id),
            'results_exported': rows_count,
            'duration_ms': log.duration_ms
        }
    except Exception as exc:
        logger.error(f"export_session_results_task xatosi: {exc}")
        raise self.retry(exc=exc)


@shared_task(
    queue='sync_sheets',
    name='apps.sheets_sync.tasks.poll_sheet_changes_task'
)
def poll_sheet_changes_task():
    """
    Celery Beat orqali muntazam ishga tushadigan fon tekshiruvi.
    Faol 'two_way' jadvallarni sinxronlashtirish vazifalarini navbatga qo'yadi.
    """
    logger.info("Celery Beat: poll_sheet_changes_task ishga tushdi.")
    active_mappings = SheetMapping.objects.filter(is_active=True, sync_direction='two_way', quiz__isnull=False)
    triggered_count = 0

    for mapping in active_mappings:
        sync_quiz_from_sheet_task.delay(
            quiz_id=str(mapping.quiz.id),
            sheet_url=mapping.sheet_url,
            worksheet_title=mapping.worksheet_title
        )
        triggered_count += 1

    return {'triggered_tasks': triggered_count}
