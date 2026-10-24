import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from questions_registry import question_registry, QuestionValidationError


class Quiz(models.Model):
    """
    Quiz model representing an interactive question set / test collection.
    Supports draft/published workflows, version snapshots, and privacy controls.
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
        verbose_name="Muallif / Egasi"
    )
    title = models.CharField(max_length=255, verbose_name="Sarlavha")
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
    is_public = models.BooleanField(default=False, verbose_name="Ommaviy")
    google_sheet_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Google Sheet URL")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Viktorina (Quiz)"
        verbose_name_plural = "Viktorinalar (Quizzes)"
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["subject", "grade_level"]),
        ]

    def __str__(self):
        return f"{self.title} (v{self.current_version})"

    @property
    def total_questions(self) -> int:
        return self.questions.count()

    @property
    def total_points(self) -> int:
        return sum(self.questions.values_list("points", flat=True))


class Question(models.Model):
    """
    Universal Canonical Question model.
    Stores any of the 29 supported question types using JSON configuration.
    Features AI lock protection (is_locked) and server-level schema validation.
    """

    DIFFICULTY_CHOICES = (
        ("easy", "Oson (Easy)"),
        ("medium", "O'rtacha (Medium)"),
        ("hard", "Qiyin (Hard)"),
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
    media_url = models.URLField(max_length=500, blank=True, null=True, verbose_name="Media URL")
    media_type = models.CharField(max_length=20, blank=True, null=True, verbose_name="Media turi")
    options = models.JSONField(default=list, blank=True, verbose_name="Variantlar")
    correct_answer = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="To'g'ri javob kaliti (Maxfiy)"
    )
    accepted_alternatives = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Muqobil javoblar"
    )
    explanation = models.TextField(blank=True, null=True, verbose_name="Izoh")
    points = models.IntegerField(default=1000, verbose_name="Baza ball")
    time_limit_seconds = models.IntegerField(default=30, verbose_name="Vaqt (soniya)")
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="medium",
        verbose_name="Qiyinlik darajasi"
    )
    order_index = models.IntegerField(default=0, verbose_name="Tartib raqami")
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Qulflangan (AI/Avto tahrirdan himoya)"
    )
    version = models.IntegerField(default=1, verbose_name="Versiya")

    class Meta:
        ordering = ["order_index"]
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"
        indexes = [
            models.Index(fields=["quiz", "order_index"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"[{self.type}] {self.prompt[:50]}... (#{self.order_index})"

    def clean(self):
        """
        Validates question payload against the QuestionTypeRegistry.
        """
        super().clean()

        if not self.prompt or not self.prompt.strip():
            raise ValidationError({"prompt": "Savol matni bo'sh bo'lishi mumkin emas."})

        if self.time_limit_seconds < 5 or self.time_limit_seconds > 300:
            raise ValidationError({
                "time_limit_seconds": "Vaqt chegarasi 5 dan 300 soniyagacha bo'lishi shart."
            })

        if self.points < 0:
            raise ValidationError({"points": "Ball manfiy bo'lishi mumkin emas."})

        # Validate with registered question type handler
        if not question_registry.is_registered(self.type):
            raise ValidationError({
                "type": f"'{self.type}' nomli savol turi registratsiyadan o'tmagan."
            })

        handler = question_registry.get(self.type)
        try:
            handler.validate_payload(self.options, self.correct_answer)
        except QuestionValidationError as exc:
            raise ValidationError({"payload": exc.message}) from exc

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_handler(self):
        return question_registry.get(self.type)

    def evaluate(self, submission):
        handler = self.get_handler()
        return handler.check_answer(submission, self.correct_answer, options=self.options)


class QuizVersion(models.Model):
    """
    Immutable snapshot of a Quiz at a specific point in time / session start.
    Ensures that active live sessions or historical reports are never broken
    when a teacher edits questions afterwards.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="Viktorina"
    )
    version_number = models.IntegerField(verbose_name="Versiya raqami")
    title = models.CharField(max_length=255, verbose_name="Sarlavha")
    snapshot_data = models.JSONField(verbose_name="To'liq muzlatilgan snapshot")
    change_log = models.TextField(blank=True, null=True, verbose_name="O'zgarishlar jurnali")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Versiya yaratuvchisi"
    )

    class Meta:
        ordering = ["-version_number"]
        unique_together = ("quiz", "version_number")
        verbose_name = "Viktorina Versiyasi (Snapshot)"
        verbose_name_plural = "Viktorina Versiyalari"

    def __str__(self):
        return f"{self.quiz.title} - Snapshot v{self.version_number}"
