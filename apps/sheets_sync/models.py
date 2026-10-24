import uuid
from django.db import models


class SheetMapping(models.Model):
    """
    Viktorina va Google Sheets jadvali o'rtasidagi bog'lanish modeli.
    """
    SYNC_MODE_CHOICES = (
        ("import", "Faqat Import (Jadval -> Baza)"),
        ("export", "Faqat Eksport (Baza -> Jadval)"),
        ("bidirectional", "Ikki tomonlama sinxronizatsiya"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.OneToOneField(
        "quizzes.Quiz",
        on_delete=models.CASCADE,
        related_name="sheet_mapping",
        verbose_name="Viktorina",
    )
    spreadsheet_id = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name="Google Spreadsheet ID",
    )
    spreadsheet_url = models.URLField(
        max_length=500,
        verbose_name="Google Sheet Havolasi",
    )
    sheet_name = models.CharField(
        max_length=100,
        default="Sheet1",
        verbose_name="Varaq Nomi",
    )
    sync_mode = models.CharField(
        max_length=30,
        choices=SYNC_MODE_CHOICES,
        default="bidirectional",
        verbose_name="Sinxronlash Rejimi",
    )
    auto_sync = models.BooleanField(
        default=True,
        verbose_name="Avtomatik sinxronlash",
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Oxirgi sinxronlash vaqti",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Jadval Bog'lanishi"
        verbose_name_plural = "Jadval Bog'lanishlari"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.quiz.title} <-> {self.spreadsheet_id}"


class SheetSyncLog(models.Model):
    """
    Har bir Google Sheets sinxronlash operatsiyasining audit jurnali.
    """
    DIRECTION_CHOICES = (
        ("import", "Import (Sheet -> DB)"),
        ("export", "Eksport (DB -> Sheet)"),
    )
    STATUS_CHOICES = (
        ("SUCCESS", "Muvaffaqiyatli"),
        ("FAILED", "Xatolik yuz berdi"),
        ("CONFLICT", "Ziddiyat aniqlandi"),
        ("LOCKED", "Boshqa jarayon tomonidan qulflangan"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mapping = models.ForeignKey(
        SheetMapping,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
        verbose_name="Bog'lanish",
    )
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sheet_sync_logs",
        verbose_name="Viktorina",
    )
    direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        verbose_name="Yo'nalish",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="SUCCESS",
        db_index=True,
        verbose_name="Holat",
    )
    rows_processed = models.IntegerField(
        default=0,
        verbose_name="Qayta ishlangan qatorlar soni",
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name="Xatolik matni",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sinxronlash Jurnali"
        verbose_name_plural = "Sinxronlash Jurnallari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.direction} - {self.quiz_id} ({self.created_at})"
