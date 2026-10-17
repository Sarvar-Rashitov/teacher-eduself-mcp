# apps/quizzes/models.py
# Backend.md §2.2 va QUIZ_ENGINE.md §2 asosida
import uuid
from django.conf import settings
from django.db import models


class Quiz(models.Model):
    """
    Viktorina modeli — dars testlari va interaktiv mashg'ulotlar to'plami.
    """
    STATUS_CHOICES = (
        ('draft', 'Qoralama'),
        ('published', 'Nashr etilgan'),
        ('archived', 'Arxivlangan'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quizzes',
        verbose_name="Egasi (O'qituvchi)"
    )
    title = models.CharField(max_length=255, verbose_name="Sarlavha")
    description = models.TextField(blank=True, default='', verbose_name="Tavsif")
    subject = models.CharField(max_length=100, db_index=True, verbose_name="Fan")
    grade_level = models.IntegerField(default=7, verbose_name="Sinf darajasi")
    locale = models.CharField(max_length=10, default='uz-Latn', verbose_name="Til")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    current_version = models.IntegerField(default=1, verbose_name="Joriy versiya")
    google_sheet_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Google Sheet URL")
    is_public = models.BooleanField(default=False, verbose_name="Ommaviy")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Viktorina"
        verbose_name_plural = "Viktorinalar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['subject']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()}, v{self.current_version})"

    @property
    def question_count(self) -> int:
        return self.questions.count()


class Question(models.Model):
    """
    Yagona universal savol modeli (29 xil turdagi savollarni JSON orqali saqlaydi).
    """
    DIFFICULTY_CHOICES = (
        ('easy', 'Oson'),
        ('medium', 'O‘rtacha'),
        ('hard', 'Qiyin'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name="Viktorina"
    )
    type = models.CharField(max_length=50, db_index=True, verbose_name="Savol turi")
    prompt = models.TextField(verbose_name="Savol matni")
    media_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Media URL")
    media_type = models.CharField(max_length=20, blank=True, null=True, verbose_name="Media turi")  # image, audio, video
    options = models.JSONField(default=list, verbose_name="Variantlar")
    correct_answer = models.JSONField(verbose_name="Maxfiy to'g'ri javob")
    accepted_alternatives = models.JSONField(default=list, blank=True, verbose_name="Qabul qilinadigan alternativlar")
    explanation = models.TextField(blank=True, default='', verbose_name="Tushuntirish / Izoh")
    points = models.IntegerField(default=1000, verbose_name="Maksimal ball")
    time_limit_seconds = models.IntegerField(default=30, verbose_name="Vaqt chegarasi (soniya)")
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    order_index = models.IntegerField(default=0, db_index=True, verbose_name="Tartib raqami")
    is_locked = models.BooleanField(default=False, verbose_name="AI tahriridan qulflangan")
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ['order_index']
        indexes = [
            models.Index(fields=['quiz', 'order_index']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"[{self.type}] {self.prompt[:40]}... ({self.points} ball)"


class QuizVersion(models.Model):
    """
    Quiz snapshot modeli — jonli sessiyalar va tarixiy hisobotlarning
    o'zgarmasligini (immutability) ta'minlash uchun xizmat qiladi.
    QUIZ_ENGINE.md §4 asosida.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name="Viktorina"
    )
    version_number = models.IntegerField(verbose_name="Versiya raqami")
    snapshot_data = models.JSONField(verbose_name="Muzlatilgan butun quiz holati")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quiz Versiyasi Snapshot"
        verbose_name_plural = "Quiz Versiyalari Snapshotlari"
        ordering = ['-version_number']
        unique_together = ('quiz', 'version_number')

    def __str__(self):
        return f"{self.quiz.title} - Snapshot v{self.version_number}"
