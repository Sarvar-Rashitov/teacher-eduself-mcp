"""
Quiz and Question ORM Models for EduSelf Teacher.
Defines Quiz, Question (Universal Canonical Schema with is_locked), and QuizVersion snapshots.
"""

import uuid
from django.db import models
from django.conf import settings


class Quiz(models.Model):
    """
    Quiz entity created by a teacher.
    Stores metadata, subject, grade level, status, and tracking information.
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
        verbose_name="Muallif o‘qituvchi"
    )
    title = models.CharField(max_length=255, verbose_name="Viktorina nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsif")
    subject = models.CharField(max_length=100, db_index=True, verbose_name="Fan")
    grade_level = models.IntegerField(default=7, verbose_name="Sinf darajasi")
    locale = models.CharField(max_length=10, default='uz-Latn', verbose_name="Til")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Holati")
    current_version = models.IntegerField(default=1, verbose_name="Joriy versiya")
    google_sheet_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Google Sheet havolasi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Oxirgi tahrir")

    class Meta:
        verbose_name = "Viktorina"
        verbose_name_plural = "Viktorinalar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subject']),
            models.Index(fields=['owner', 'status']),
        ]

    def __str__(self):
        return f"{self.title} (v{self.current_version})"

    @property
    def question_count(self) -> int:
        return self.questions.count()


class Question(models.Model):
    """
    Universal question entity adhering to the 29 question type specifications.
    Holds options, secret correct_answer key, and is_locked protection flag.
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
    media_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Media havolasi")
    media_type = models.CharField(max_length=20, blank=True, null=True, verbose_name="Media turi")
    options = models.JSONField(default=list, verbose_name="Variantlar ro‘yxati")
    correct_answer = models.JSONField(verbose_name="To‘g‘ri javob kaliti")  # Secret key!
    accepted_alternatives = models.JSONField(default=list, blank=True, verbose_name="Muqobil to‘g‘ri javoblar")
    explanation = models.TextField(blank=True, null=True, verbose_name="Izoh / Tushuntirish")
    points = models.IntegerField(default=1000, verbose_name="Baza ball")
    time_limit_seconds = models.IntegerField(default=30, verbose_name="Vaqt limiti (soniya)")
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium', verbose_name="Murakkablik")
    order_index = models.IntegerField(default=0, verbose_name="Tartib raqami")
    is_locked = models.BooleanField(default=False, verbose_name="Qulflangan (AI daxlsizligi)")
    version = models.IntegerField(default=1, verbose_name="Savol versiyasi")

    class Meta:
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        ordering = ['order_index']
        indexes = [
            models.Index(fields=['quiz', 'order_index']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f"{self.order_index + 1}. [{self.type}] {self.prompt[:50]}"


class QuizVersion(models.Model):
    """
    Frozen snapshot of a quiz at a specific published version.
    Guarantees immutability and report reproducibility for live sessions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name="Viktorina"
    )
    version_number = models.IntegerField(verbose_name="Versiya raqami")
    snapshot_data = models.JSONField(default=dict, verbose_name="Snapshot ma’lumotlari")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        verbose_name = "Viktorina Versiyasi Snapshot"
        verbose_name_plural = "Viktorina Versiyalari Snapshotlari"
        unique_together = ('quiz', 'version_number')
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.quiz.title} v{self.version_number} snapshot"
