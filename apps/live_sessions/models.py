# apps/live_sessions/models.py
# Backend.md §2.3 va LIVE_SESSION.md §2 asosida
import uuid
from django.conf import settings
from django.db import models


class LiveSession(models.Model):
    """
    Jonli dars sessiyasi modeli.
    O'qituvchi va o'quvchilarni yagona xonaga (room_code) birlashtiradi.
    """
    STATUS_CHOICES = (
        ('draft', 'Qoralama'),
        ('lobby', 'Kutish zali (Lobby)'),
        ('in_progress', 'Faol o‘yin (In Progress)'),
        ('paused', 'To‘xtatilgan (Paused)'),
        ('completed', 'Yakunlangan (Completed)'),
        ('cancelled', 'Bekor qilingan (Cancelled)'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(
        'quizzes.Quiz',
        on_delete=models.CASCADE,
        related_name='live_sessions',
        verbose_name="Viktorina"
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hosted_sessions',
        verbose_name="Boshlovchi (O'qituvchi)"
    )
    room_code = models.CharField(
        max_length=6,
        unique=True,
        db_index=True,
        verbose_name="Xona PIN kodi"
    )
    game_mode = models.CharField(max_length=50, default='classic', verbose_name="O'yin rejimi")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True,
        verbose_name="Holat"
    )
    current_question_index = models.IntegerField(default=0, verbose_name="Joriy savol indeksi")
    current_question_deadline = models.FloatField(null=True, blank=True, verbose_name="Server taymer deadline (ts)")
    is_lobby_locked = models.BooleanField(default=False, verbose_name="Lobby qulflangan")
    settings_payload = models.JSONField(default=dict, blank=True, verbose_name="Sessiya sozlamalari")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Boshlangan vaqt")
    ended_at = models.DateTimeField(null=True, blank=True, verbose_name="Yakunlangan vaqt")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Jonli Sessiya"
        verbose_name_plural = "Jonli Sessiyalar"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room_code', 'status']),
            models.Index(fields=['host', 'status']),
        ]

    def __str__(self):
        return f"Xona #{self.room_code} - {self.quiz.title} ({self.get_status_display()})"

    @property
    def participant_count(self) -> int:
        return self.participants.count()


class Participant(models.Model):
    """
    Sessiyada qatnashayotgan o'quvchi (ishtirokchi).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='participants',
        verbose_name="Sessiya"
    )
    nickname = models.CharField(max_length=50, verbose_name="Taxallus (Ism)")
    team_name = models.CharField(max_length=50, blank=True, null=True, verbose_name="Jamoa nomi")
    anonymous_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="Anonim sessiya tokeni"
    )
    score = models.IntegerField(default=0, db_index=True, verbose_name="Ball")
    streak = models.IntegerField(default=0, verbose_name="Ketma-ket to'g'ri javoblar")
    is_connected = models.BooleanField(default=True, verbose_name="Ulangan")
    last_seen_seq = models.IntegerField(default=0, verbose_name="Oxirgi qabul qilingan event seq")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ishtirokchi"
        verbose_name_plural = "Ishtirokchilar"
        ordering = ['-score']
        unique_together = ('session', 'nickname')

    def __str__(self):
        return f"{self.nickname} ({self.score} ball, Xona #{self.session.room_code})"


class AnswerSubmission(models.Model):
    """
    O'quvchi tomonidan yuborilgan javob yozuvi.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='submissions',
        verbose_name="Sessiya"
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='submissions',
        verbose_name="Ishtirokchi"
    )
    question_id = models.UUIDField(db_index=True, verbose_name="Savol ID")
    submitted_payload = models.JSONField(verbose_name="Yuborilgan javob varianti")
    is_correct = models.BooleanField(default=False, verbose_name="To'g'riligi")
    points_awarded = models.IntegerField(default=0, verbose_name="Berilgan ball")
    response_time_ms = models.IntegerField(default=0, verbose_name="Javob berish tezligi (ms)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Javob Yuborilishi"
        verbose_name_plural = "Javob Yuborilishlari"
        unique_together = ('session', 'participant', 'question_id')
        indexes = [
            models.Index(fields=['session', 'question_id']),
        ]

    def __str__(self):
        return f"{self.participant.nickname} -> Q:{self.question_id} ({'+' if self.is_correct else ''}{self.points_awarded})"
