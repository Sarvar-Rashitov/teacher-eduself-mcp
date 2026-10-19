"""
ORM Models for Google Sheets Synchronization (Phase 09).
Tracks spreadsheet mappings, sync status, and immutable audit logs.
"""

import uuid
from django.db import models
from django.conf import settings


class SheetMapping(models.Model):
    """
    Connects a Quiz (and its live sessions) to a specific Google Sheet.
    Tracks sync direction, automation preferences, and health status.
    """
    DIRECTION_CHOICES = (
        ('bidirectional', 'Ikki tomonlama (Import & Export)'),
        ('import_only', 'Faqat Import (Jadvaldan bazaga)'),
        ('export_only', 'Faqat Eksport (Bazadan jadvalga)'),
    )

    STATUS_CHOICES = (
        ('idle', 'Kutilmoqda (Idle)'),
        ('syncing', 'Sinxronlanmoqda (Syncing)'),
        ('success', 'Muvaffaqiyatli (Success)'),
        ('failed', 'Xatolik (Failed)'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        'quizzes.Quiz',
        on_delete=models.CASCADE,
        related_name='sheet_mappings',
        verbose_name="Viktorina"
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sheet_mappings',
        verbose_name="O‘qituvchi"
    )
    spreadsheet_id = models.CharField(max_length=255, db_index=True, verbose_name="Google Spreadsheet ID")
    spreadsheet_url = models.URLField(max_length=500, verbose_name="Jadval havolasi")
    sheet_name = models.CharField(max_length=150, default='Questions', verbose_name="Varaq nomi (Worksheet)")
    results_sheet_name = models.CharField(max_length=150, default='Results', verbose_name="Natijalar varag‘i")
    sync_direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        default='bidirectional',
        verbose_name="Sinxronlash yo‘nalishi"
    )
    auto_sync_on_session_end = models.BooleanField(
        default=True,
        verbose_name="Dars tugashi bilan natijalarni avtomatik jadvalga yozish"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol holatda")
    last_synced_at = models.DateTimeField(null=True, blank=True, verbose_name="Oxirgi muvaffaqiyatli sinxronlash")
    sync_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='idle',
        verbose_name="Sinxronlash holati"
    )
    last_error = models.TextField(blank=True, null=True, verbose_name="So‘nggi xatolik matni")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Tahrirlangan vaqt")

    class Meta:
        verbose_name = "Google Sheet Birikmasi"
        verbose_name_plural = "Google Sheet Birikmalari"
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['teacher', 'is_active']),
            models.Index(fields=['quiz', 'is_active']),
            models.Index(fields=['spreadsheet_id']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['quiz', 'spreadsheet_id'],
                name='unique_quiz_spreadsheet_mapping'
            )
        ]

    def __str__(self):
        return f"{self.quiz.title} ↔ {self.sheet_name} ({self.sync_status})"


class SheetSyncLog(models.Model):
    """
    Immutable audit log for every sync attempt between EduSelf and Google Sheets.
    Records duration, rows processed, status, and error details.
    """
    SYNC_TYPE_CHOICES = (
        ('export_quiz', 'Viktorina eksporti'),
        ('import_quiz', 'Viktorina importi'),
        ('export_session_results', 'Dars natijalari eksporti'),
        ('poll_changes', 'Davriy jadval tekshiruvi'),
    )

    STATUS_CHOICES = (
        ('success', 'Muvaffaqiyatli'),
        ('failed', 'Muvaffaqiyatsiz'),
        ('in_progress', 'Jarayonda'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mapping = models.ForeignKey(
        SheetMapping,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name="Jadval birikmasi"
    )
    quiz = models.ForeignKey(
        'quizzes.Quiz',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sheet_sync_logs',
        verbose_name="Viktorina"
    )
    session = models.ForeignKey(
        'live_sessions.LiveSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sheet_sync_logs',
        verbose_name="Jonli sessiya"
    )
    sync_type = models.CharField(max_length=30, choices=SYNC_TYPE_CHOICES, verbose_name="Sinxronlash turi")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress', verbose_name="Holati")
    rows_processed = models.IntegerField(default=0, verbose_name="Qayta ishlangan qatorlar")
    duration_ms = models.IntegerField(default=0, verbose_name="Bajarilish vaqti (ms)")
    error_details = models.TextField(blank=True, null=True, verbose_name="Xatolik tafsilotlari")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Boshlangan vaqt")

    class Meta:
        verbose_name = "Sinxronlash Jurnali"
        verbose_name_plural = "Sinxronlash Jurnallari"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['quiz', 'sync_type']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.status.upper()}] {self.sync_type} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
