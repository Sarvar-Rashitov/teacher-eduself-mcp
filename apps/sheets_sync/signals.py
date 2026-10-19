"""
Signals for Google Sheets Synchronization.
Automatically exports live game session results when session.status becomes 'completed'.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.live_sessions.models import LiveSession
from apps.sheets_sync.tasks import export_session_results_task

logger = logging.getLogger(__name__)


@receiver(post_save, sender=LiveSession)
def on_live_session_completed(sender, instance: LiveSession, created: bool, **kwargs):
    """
    Triggered when a LiveSession is saved.
    If the session is completed and has a linked Google Sheet, triggers Celery export task.
    """
    if instance.status == LiveSession.STATUS_COMPLETED:
        quiz = instance.quiz
        has_sheet = bool(quiz.google_sheet_url)
        mapping = quiz.sheet_mappings.filter(is_active=True, auto_sync_on_session_end=True).first()

        if has_sheet or mapping:
            logger.info(f"Triggering auto Google Sheets gradebook export for completed session {instance.room_code}")
            export_session_results_task.delay(str(instance.id))
