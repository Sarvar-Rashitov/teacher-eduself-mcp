"""
Celery asynchronous tasks for Google Sheets synchronization.
Provides retry mechanisms with exponential backoff and distributed lock handling.
"""

import logging
from typing import Any, Dict, Optional
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist

from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.sheets_sync.models import SheetMapping, SheetSyncLog
from apps.sheets_sync.services import (
    GoogleSheetsSyncService,
    SyncLockAcquisitionError,
)

logger = logging.getLogger("sheets_sync.tasks")


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def export_quiz_to_sheet_task(
    self,
    quiz_id: str,
    spreadsheet_url: str,
    worksheet_name: str = "Sheet1",
) -> Dict[str, Any]:
    """
    Viktorina savollarini Google Sheet jadvaliga fon rejimida eksport qilish.
    """
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        service = GoogleSheetsSyncService()
        rows_count = service.export_quiz_to_sheet(
            quiz=quiz,
            spreadsheet_url=spreadsheet_url,
            worksheet_name=worksheet_name,
        )
        logger.info(f"Quiz {quiz_id} exported to sheets successfully. Rows: {rows_count}")
        return {
            "status": "SUCCESS",
            "quiz_id": quiz_id,
            "rows_exported": rows_count,
            "spreadsheet_url": spreadsheet_url,
        }
    except SyncLockAcquisitionError as e:
        logger.warning(f"Lock active for quiz {quiz_id}, retrying export in 15s...")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=15)
        return {"status": "LOCKED", "quiz_id": quiz_id, "error": str(e)}
    except ObjectDoesNotExist as e:
        logger.error(f"Quiz {quiz_id} not found: {e}")
        return {"status": "FAILED", "quiz_id": quiz_id, "error": "Quiz topilmadi"}
    except Exception as exc:
        logger.error(f"Export error for quiz {quiz_id}: {exc}")
        if self.request.retries < self.max_retries:
            backoff = 10 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=backoff)
        return {"status": "FAILED", "quiz_id": quiz_id, "error": str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def import_sheet_to_quiz_task(
    self,
    quiz_id: str,
    spreadsheet_url: str,
    worksheet_name: str = "Sheet1",
) -> Dict[str, Any]:
    """
    Google Sheet jadvalidan savollarni o'qib bazaga import qilish vazifasi.
    """
    try:
        quiz = Quiz.objects.get(id=quiz_id)
        service = GoogleSheetsSyncService()
        imported_count = service.import_sheet_to_quiz(
            quiz=quiz,
            spreadsheet_url=spreadsheet_url,
            worksheet_name=worksheet_name,
        )
        logger.info(f"Quiz {quiz_id} imported from sheets successfully. Questions: {imported_count}")
        return {
            "status": "SUCCESS",
            "quiz_id": quiz_id,
            "rows_imported": imported_count,
            "spreadsheet_url": spreadsheet_url,
        }
    except SyncLockAcquisitionError as e:
        logger.warning(f"Lock active for quiz {quiz_id}, retrying import in 15s...")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=15)
        return {"status": "LOCKED", "quiz_id": quiz_id, "error": str(e)}
    except ObjectDoesNotExist as e:
        logger.error(f"Quiz {quiz_id} not found: {e}")
        return {"status": "FAILED", "quiz_id": quiz_id, "error": "Quiz topilmadi"}
    except Exception as exc:
        logger.error(f"Import error for quiz {quiz_id}: {exc}")
        if self.request.retries < self.max_retries:
            backoff = 10 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=backoff)
        return {"status": "FAILED", "quiz_id": quiz_id, "error": str(exc)}


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def sync_live_session_results_task(
    self,
    session_id: str,
    spreadsheet_url: str,
    worksheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tugallangan jonli dars natijalarini Google Sheets ga eksport qilish vazifasi.
    """
    try:
        session = LiveSession.objects.select_related("quiz").prefetch_related("participants").get(id=session_id)
        service = GoogleSheetsSyncService()
        count = service.sync_live_scores_to_sheet(
            session=session,
            spreadsheet_url=spreadsheet_url,
            worksheet_name=worksheet_name,
        )
        logger.info(f"Session {session_id} results exported to sheets: {count} rows")
        return {
            "status": "SUCCESS",
            "session_id": session_id,
            "rows_exported": count,
            "spreadsheet_url": spreadsheet_url,
        }
    except ObjectDoesNotExist as e:
        logger.error(f"LiveSession {session_id} not found: {e}")
        return {"status": "FAILED", "session_id": session_id, "error": "Sessiya topilmadi"}
    except Exception as exc:
        logger.error(f"Session results sync error: {exc}")
        if self.request.retries < self.max_retries:
            backoff = 10 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=backoff)
        return {"status": "FAILED", "session_id": session_id, "error": str(exc)}


@shared_task(bind=True)
def poll_sheet_changes(self) -> Dict[str, Any]:
    """
    Celery Beat orqali muntazam ishga tushadigan fon tekshiruvi.
    Barcha auto_sync=True bo'lgan bog'lanishlarni tekshirib, import vazifalarini chaqiradi.
    """
    mappings = SheetMapping.objects.filter(
        auto_sync=True,
        sync_mode__in=["import", "bidirectional"],
    ).select_related("quiz")

    dispatched = 0
    for mapping in mappings:
        import_sheet_to_quiz_task.delay(
            quiz_id=str(mapping.quiz.id),
            spreadsheet_url=mapping.spreadsheet_url,
            worksheet_name=mapping.sheet_name,
        )
        dispatched += 1

    return {"status": "SUCCESS", "tasks_dispatched": dispatched}


# Development plan and backwards-compatibility alias
sync_quiz_to_sheet = export_quiz_to_sheet_task
