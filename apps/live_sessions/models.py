import uuid
from django.db import models
from django.conf import settings


class LiveSession(models.Model):
    """
    Live interactive classroom session.
    Represents a real-time game room orchestrated by a host teacher and joined
    by student participants via room code / PIN.
    """

    STATUS_CHOICES = (
        ("draft", "Qoralama (Draft)"),
        ("lobby", "Kutish Zali (Lobby)"),
        ("active", "Faol (Active/In Progress)"),
        ("paused", "Pauzada (Paused)"),
        ("completed", "Yakunlangan (Completed)"),
        ("cancelled", "Bekor qilingan (Cancelled)"),
    )

    FSM_STATE_CHOICES = (
        ("lobby", "Lobby"),
        ("question_preview", "Question Preview (3-2-1)"),
        ("question_open", "Question Open"),
        ("question_closed", "Question Closed"),
        ("answer_reveal", "Answer Reveal"),
        ("round_leaderboard", "Round Leaderboard"),
        ("summary", "Summary / Podium"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.CASCADE,
        related_name="live_sessions",
        verbose_name="Tegishli viktorina"
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hosted_sessions",
        verbose_name="Boshlovchi (O'qituvchi)"
    )
    room_code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        verbose_name="Xona PIN kodi (6 raqam)"
    )
    game_mode = models.CharField(max_length=50, default="classic", verbose_name="O'yin rejimi")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        verbose_name="Sessiya holati"
    )
    fsm_state = models.CharField(
        max_length=30,
        choices=FSM_STATE_CHOICES,
        default="lobby",
        verbose_name="FSM ichki holati"
    )
    current_question_index = models.IntegerField(default=0, verbose_name="Joriy savol indeksi")
    is_locked = models.BooleanField(default=False, verbose_name="Xona qulflangan (Lobby Locked)")
    question_deadline_ts = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="Savol tugash vaqti (ms)"
    )
    settings_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Xona sozlamalari (JSON)"
    )
    snapshot_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Muzlatilgan viktorina snapshot'i"
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Boshlangan vaqti")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Yakunlangan vaqti")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Jonli Sessiya"
        verbose_name_plural = "Jonli Sessiyalar"
        indexes = [
            models.Index(fields=["room_code"]),
            models.Index(fields=["status"]),
            models.Index(fields=["host", "status"]),
        ]

    def __str__(self):
        return f"Sessiya {self.room_code} ({self.get_status_display()})"

    @property
    def total_participants(self) -> int:
        return self.participants.filter(is_kicked=False).count()

    @property
    def channel_group_name(self) -> str:
        return f"room_{self.room_code}"


class Participant(models.Model):
    """
    Participant in a LiveSession.
    May be an anonymous student with a nickname or an authenticated user.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Sessiya"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_participations",
        verbose_name="Foydalanuvchi"
    )
    nickname = models.CharField(max_length=50, verbose_name="Ism / Taxallus")
    team_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="Jamoa nomi")
    anonymous_token = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="Qayta ulanish tokeni"
    )
    score = models.IntegerField(default=0, verbose_name="Umumiy ball")
    current_streak = models.IntegerField(default=0, verbose_name="Ketma-ket to'g'ri javoblar")
    is_connected = models.BooleanField(default=True, verbose_name="Ulanganmi?")
    is_kicked = models.BooleanField(default=False, verbose_name="Haydalganmi (Kicked)?")
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score", "joined_at"]
        verbose_name = "Ishtirokchi"
        verbose_name_plural = "Ishtirokchilar"
        indexes = [
            models.Index(fields=["session", "anonymous_token"]),
            models.Index(fields=["session", "score"]),
        ]

    def __str__(self):
        return f"{self.nickname} ({self.score} pts) - {self.session.room_code}"


class AnswerSubmission(models.Model):
    """
    Student answer submission record.
    Enforces idempotency (single answer per question per participant) and records latency.
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
    question_id = models.CharField(max_length=64, db_index=True, verbose_name="Savol ID")
    submission_id = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="Mijoz Idempotentlik ID"
    )
    response_data = models.JSONField(verbose_name="Talaba javobi")
    is_correct = models.BooleanField(default=False, verbose_name="To'g'rimi?")
    score_awarded = models.IntegerField(default=0, verbose_name="Berilgan ball")
    client_submit_ts = models.BigIntegerField(null=True, blank=True, verbose_name="Mijoz vaqti (ms)")
    server_latency_ms = models.IntegerField(default=0, verbose_name="Server kechikishi (ms)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        unique_together = ("session", "participant", "question_id")
        verbose_name = "Javob Qabul Qilishi"
        verbose_name_plural = "Javob Qabul Qilishlari"
        indexes = [
            models.Index(fields=["session", "question_id"]),
            models.Index(fields=["submission_id"]),
        ]

    def __str__(self):
        return f"{self.participant.nickname} -> Q:{self.question_id} ({'To`g`ri' if self.is_correct else 'Noto`g`ri'})"
