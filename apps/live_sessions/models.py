import uuid
from django.db import models
from django.conf import settings


class LiveSession(models.Model):
    """
    Jonli o'yin sessiyasi modeli.
    O'qituvchi, proyektor va o'quvchilarni yagona xonaga (room_code) birlashtiradi.
    """
    STATUS_CHOICES = (
        ("draft", "Qoralama"),
        ("lobby", "Lobbida"),
        ("active", "Faol"),
        ("paused", "Pauzada"),
        ("completed", "Tugallangan"),
        ("cancelled", "Bekor qilingan"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.CASCADE,
        related_name="live_sessions",
        verbose_name="Viktorina"
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hosted_sessions",
        verbose_name="O'qituvchi (Host)"
    )
    room_code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        verbose_name="Xona PIN kodi"
    )
    game_mode = models.CharField(
        max_length=50,
        default="classic",
        verbose_name="O'yin rejimi"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
        verbose_name="Holat"
    )
    settings_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Sessiya konfiguratsiyasi"
    )
    current_question_index = models.IntegerField(
        default=0,
        verbose_name="Joriy savol indeksi"
    )
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Xona qulflangan (yangi kiruvchilar to'xtatilgan)"
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Boshlangan vaqti")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Yakunlangan vaqti")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Jonli Sessiya"
        verbose_name_plural = "Jonli Sessiyalar"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["room_code", "status"]),
            models.Index(fields=["host", "status"]),
        ]

    def __str__(self):
        return f"Sessiya {self.room_code} ({self.get_status_display()}) - {self.quiz.title}"


class Participant(models.Model):
    """
    Sessiya ishtirokchisi (O'quvchi).
    Har bir o'quvchi xavfsiz anonymous_token orqali qayta ulanish imkoniga ega.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Sessiya"
    )
    nickname = models.CharField(max_length=50, verbose_name="Taxallus")
    team_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="Jamoa nomi")
    anonymous_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Anonim tiklanish tokeni"
    )
    score = models.IntegerField(default=0, db_index=True, verbose_name="To'plangan ball")
    streak = models.IntegerField(default=0, verbose_name="Ketma-ket to'g'ri javoblar")
    is_connected = models.BooleanField(default=True, verbose_name="Ulanganlik holati")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ishtirokchi"
        verbose_name_plural = "Ishtirokchilar"
        ordering = ["-score", "joined_at"]
        indexes = [
            models.Index(fields=["session", "score"]),
            models.Index(fields=["session", "is_connected"]),
        ]

    def __str__(self):
        return f"{self.nickname} ({self.score} ball) - {self.session.room_code}"


class AnswerSubmission(models.Model):
    """
    Ishtirokchilar tomonidan yuborilgan javoblar.
    submission_id idempotency kaliti orqali takroriy jo'natilishdan himoyalangan.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Sessiya"
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Ishtirokchi"
    )
    question = models.ForeignKey(
        "quizzes.Question",
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="Savol"
    )
    submission_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Takrorlanmas yuborish ID si (Idempotency Key)"
    )
    user_answer = models.JSONField(verbose_name="Talaba javobi")
    is_correct = models.BooleanField(default=False, verbose_name="To'g'rimi")
    score_awarded = models.IntegerField(default=0, verbose_name="Berilgan ball")
    time_taken_ms = models.IntegerField(default=0, verbose_name="Sarflangan vaqt (ms)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Javob"
        verbose_name_plural = "Javoblar"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session", "question"]),
            models.Index(fields=["participant", "question"]),
        ]

    def __str__(self):
        return f"{self.participant.nickname} -> Savol {self.question_id} ({'+' if self.is_correct else '-'})"
