import uuid
from django.db import models
from django.conf import settings


class Quiz(models.Model):
    """
    Viktorina modeli.
    O'qituvchi tomonidan yaratilgan savollar to'plamini boshqaradi.
    """
    STATUS_CHOICES = (
        ("draft", "Qoralama"),
        ("published", "Nashr etilgan"),
        ("archived", "Arxivlangan"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quizzes",
        verbose_name="Muallif o'qituvchi"
    )
    title = models.CharField(max_length=255, verbose_name="Viktorina nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsif")
    subject = models.CharField(max_length=100, db_index=True, verbose_name="Fan")
    grade_level = models.IntegerField(default=7, verbose_name="Sinf")
    locale = models.CharField(max_length=10, default="uz-Latn", verbose_name="Til")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name="Holat"
    )
    current_version = models.IntegerField(default=1, verbose_name="Joriy versiya")
    google_sheet_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Google Sheets havolasi")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Viktorina"
        verbose_name_plural = "Viktorinalar"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["subject", "grade_level"]),
        ]

    def __str__(self):
        return f"{self.title} (v{self.current_version})"


class Question(models.Model):
    """
    Universal Savol modeli (Canonical Question Model).
    29 xil savol formatini JSONB maydonlar va registry pattern orqali saqlaydi.
    """
    DIFFICULTY_CHOICES = (
        ("easy", "Oson"),
        ("medium", "O'rtacha"),
        ("hard", "Qiyin"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name="Tegishli viktorina"
    )
    type = models.CharField(max_length=50, db_index=True, verbose_name="Savol turi")
    prompt = models.TextField(verbose_name="Savol matni")
    media_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Media havolasi")
    media_type = models.CharField(max_length=20, blank=True, null=True, verbose_name="Media turi")  # image, audio, video
    options = models.JSONField(default=list, blank=True, verbose_name="Variantlar")
    correct_answer = models.JSONField(verbose_name="To'g'ri javob kaliti")  # Maxfiy kalit
    accepted_alternatives = models.JSONField(default=list, blank=True, verbose_name="Qo'shimcha qabul qilinadigan javoblar")
    explanation = models.TextField(blank=True, null=True, verbose_name="Pedagogik tushuntirish")
    points = models.IntegerField(default=1000, verbose_name="Baza ball")
    time_limit_seconds = models.IntegerField(default=30, verbose_name="Vaqt chegarasi (soniya)")
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="medium",
        verbose_name="Qiyinlik darajasi"
    )
    order_index = models.IntegerField(default=0, verbose_name="Tartib raqami")
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Qulflangan (AI tahriridan himoyalangan)"
    )
    version = models.IntegerField(default=1, verbose_name="Savol versiyasi")

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ["order_index"]
        indexes = [
            models.Index(fields=["quiz", "order_index"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.order_index + 1}. {self.prompt[:40]}... ({self.type})"


class QuizVersion(models.Model):
    """
    Viktorina versiyasi (Snapshot).
    Sessiya boshlanganda o'yinni muzlatish va tahrirlash tarixini saqlash uchun.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="Viktorina"
    )
    version_number = models.IntegerField(verbose_name="Versiya raqami")
    snapshot = models.JSONField(verbose_name="Muzlatilgan holat")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Viktorina versiyasi"
        verbose_name_plural = "Viktorina versiyalari"
        unique_together = ("quiz", "version_number")
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.quiz.title} - v{self.version_number}"
