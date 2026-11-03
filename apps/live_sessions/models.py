import uuid
from django.db import models
from django.conf import settings


class LiveSession(models.Model):
    """
    Jonli sessiya modeli - O'qituvchi, proyektor va o'quvchilar xonasini ifodalaydi.
    """
    STATUS_DRAFT = 'draft'
    STATUS_LOBBY = 'lobby'
    STATUS_ACTIVE = 'active'
    STATUS_PAUSED = 'paused'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = (
        (STATUS_DRAFT, 'Draft'),
        (STATUS_LOBBY, 'Lobby'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        'quizzes.Quiz',
        on_delete=models.CASCADE,
        related_name='live_sessions'
    )
    quiz_version = models.ForeignKey(
        'quizzes.QuizVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='live_sessions'
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hosted_sessions'
    )
    room_code = models.CharField(max_length=10, unique=True, db_index=True)
    game_mode = models.CharField(max_length=50, default='classic')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_lobby_locked = models.BooleanField(default=False)
    current_question_index = models.IntegerField(default=0)
    settings_payload = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room_code', 'status']),
            models.Index(fields=['host', 'status']),
        ]

    def __str__(self):
        return f"LiveSession {self.room_code} ({self.status}) - {self.quiz.title}"


class Participant(models.Model):
    """
    Sessiyada qatnashayotgan o'quvchi / ishtirokchi modeli.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    nickname = models.CharField(max_length=50)
    team_name = models.CharField(max_length=50, blank=True, null=True)
    anonymous_token = models.CharField(max_length=64, db_index=True)
    score = models.IntegerField(default=0)
    streak = models.IntegerField(default=0)
    is_connected = models.BooleanField(default=True)
    is_kicked = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-score', 'joined_at']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'nickname'],
                name='unique_participant_nickname_per_session'
            )
        ]
        indexes = [
            models.Index(fields=['session', 'anonymous_token']),
            models.Index(fields=['session', 'score']),
        ]

    def __str__(self):
        return f"{self.nickname} ({self.score} ball) - {self.session.room_code}"


class AnswerSubmission(models.Model):
    """
    O'quvchining savolga bergan javobi (idempotent, tekshirilgan va baholangan).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    question = models.ForeignKey(
        'quizzes.Question',
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    submission_id = models.CharField(max_length=64, unique=True, db_index=True)
    response_data = models.JSONField(default=dict)
    is_correct = models.BooleanField(default=False)
    score_awarded = models.IntegerField(default=0)
    latency_ms = models.IntegerField(default=0)
    client_submit_ts = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'question']),
            models.Index(fields=['participant', 'question']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Submission {self.submission_id} by {self.participant.nickname} for Q:{self.question_id}"
