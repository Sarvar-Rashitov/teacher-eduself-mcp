import uuid
from django.db import models


class SheetMapping(models.Model):
    """
    Google Sheet jadvalining EduSelf tizimidagi Quiz yoki LiveSession bilan bog'lanishi.
    """
    DIRECTION_CHOICES = (
        ('two_way', 'Ikki tomonlama'),
        ('import_only', 'Faqat import'),
        ('export_only', 'Faqat eksport'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        'quizzes.Quiz',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sheet_mappings',
        verbose_name="Bog'langan Viktorina"
    )
    session = models.ForeignKey(
        'live_sessions.LiveSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sheet_mappings',
        verbose_name="Bog'langan Jonli Sessiya"
    )
    sheet_url = models.URLField(max_length=500, verbose_name="Google Sheet URL")
    spreadsheet_id = models.CharField(max_length=150, blank=True, db_index=True, verbose_name="Spreadsheet ID")
    worksheet_title = models.CharField(max_length=150, default='Sheet1', verbose_name="Varaq nomi")
    sync_direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        default='two_way',
        verbose_name="Sinxronizatsiya yo'nalishi"
    )
    last_synced_at = models.DateTimeField(null=True, blank=True, verbose_name="So'nggi sinxronlangan vaqt")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Google Sheet Xaritasi"
        verbose_name_plural = "Google Sheet Xaritalari"
        ordering = ['-created_at']

    def __str__(self):
        target = self.quiz.title if self.quiz else (f"Session {self.session.room_code}" if self.session else "Unlinked")
        return f"{target} ↔ {self.worksheet_title} ({self.get_sync_direction_display()})"


class SheetSyncLog(models.Model):
    """
    Har bir Google Sheet sinxronizatsiya amaliyoti auditi va tarixi.
    """
    DIRECTION_CHOICES = (
        ('sheet_to_quiz', 'Sheetdan Quizga (Import)'),
        ('quiz_to_sheet', 'Quizdan Sheetga (Export)'),
        ('session_to_sheet', 'Sessiya Natijalari Sheetga (Batch Export)'),
    )

    STATUS_CHOICES = (
        ('pending', 'Kutilmoqda'),
        ('in_progress', 'Jarayonda'),
        ('success', 'Muvaffaqiyatli'),
        ('failed', 'Xatolik'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mapping = models.ForeignKey(
        SheetMapping,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name="Xarita"
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
        verbose_name="Jonli Sessiya"
    )
    direction = models.CharField(max_length=30, choices=DIRECTION_CHOICES, verbose_name="Yo'nalish")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True, verbose_name="Holat")
    rows_processed = models.IntegerField(default=0, verbose_name="Qayta ishlangan qatorlar")
    duration_ms = models.IntegerField(default=0, verbose_name="Davomiylik (ms)")
    error_message = models.TextField(blank=True, default='', verbose_name="Xatolik xabari")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Qo'shimcha parametrlar")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Sinxronizatsiya Logi"
        verbose_name_plural = "Sinxronizatsiya Loglari"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.direction} - {self.rows_processed} qator ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
