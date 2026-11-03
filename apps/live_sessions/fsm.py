"""
Session Finite State Machine (FSM) implementation.
Manages the rigorous lifecycle of live interactive classroom sessions.
"""

from django.utils import timezone


class InvalidStateTransitionError(Exception):
    """Xato yoki ruxsat etilmagan holat o'tishi yuz berganda ko'tariladi."""
    pass


class SessionLockedError(Exception):
    """Xona qulflangan holatda ishtirokchi qo'shilmoqchi bo'lganda ko'tariladi."""
    pass


class SessionStateMachine:
    """
    Sessiya Holat Mashinasi (Server-Authoritative FSM).
    Xonaning har bir fazasi va ruxsat etilgan tranzitsiyalarini qat'iy nazorat qiladi.
    """
    # Asosiy sessiya holatlari
    STATE_DRAFT = 'draft'
    STATE_LOBBY = 'lobby'
    STATE_ACTIVE = 'active'
    STATE_PAUSED = 'paused'
    STATE_COMPLETED = 'completed'
    STATE_CANCELLED = 'cancelled'

    # Savol raundi ichki fazalari (Active holatida)
    PHASE_IDLE = 'idle'
    PHASE_PREVIEW = 'preview'
    PHASE_QUESTION_OPEN = 'question_open'
    PHASE_QUESTION_CLOSED = 'question_closed'
    PHASE_ANSWER_REVEAL = 'answer_reveal'
    PHASE_LEADERBOARD = 'leaderboard'
    PHASE_SUMMARY = 'summary'

    def __init__(self, session):
        self.session = session
        # Ichki fazani settings_payload ichidan olamiz yoki default idle
        self.round_phase = self.session.settings_payload.get('round_phase', self.PHASE_IDLE)
        self.paused_from_phase = self.session.settings_payload.get('paused_from_phase', None)

    @property
    def current_state(self) -> str:
        return self.session.status

    @property
    def current_phase(self) -> str:
        return self.round_phase

    def to_lobby(self):
        """Draft -> Lobby: O'quvchilar ulanishi uchun xonani ochish."""
        if self.session.status != self.STATE_DRAFT:
            raise InvalidStateTransitionError(
                f"Lobby holatiga faqat 'draft' holatidan o'tish mumkin, hozirgi holat: {self.session.status}"
            )
        self.session.status = self.STATE_LOBBY
        self.session.is_lobby_locked = False
        self._update_round_phase(self.PHASE_IDLE)
        self.session.save(update_fields=['status', 'is_lobby_locked', 'settings_payload', 'updated_at'])

    def lock_lobby(self):
        """Lobbyni qulflash (yangi o'quvchilar kira olmaydi)."""
        if self.session.status != self.STATE_LOBBY:
            raise InvalidStateTransitionError("Faqat lobby holatidagi xonani qulflash mumkin.")
        self.session.is_lobby_locked = True
        self.session.save(update_fields=['is_lobby_locked', 'updated_at'])

    def unlock_lobby(self):
        """Lobby qulfini ochish."""
        if self.session.status != self.STATE_LOBBY:
            raise InvalidStateTransitionError("Faqat lobby holatidagi xona qulfini ochish mumkin.")
        self.session.is_lobby_locked = False
        self.session.save(update_fields=['is_lobby_locked', 'updated_at'])

    def start_session(self):
        """Lobby -> Active: Sessiyani rasman boshlash."""
        if self.session.status != self.STATE_LOBBY:
            raise InvalidStateTransitionError(
                f"Sessiyani faqat 'lobby' holatidan boshlash mumkin, hozirgi holat: {self.session.status}"
            )
        self.session.status = self.STATE_ACTIVE
        self.session.started_at = timezone.now()
        self._update_round_phase(self.PHASE_IDLE)
        self.session.save(update_fields=['status', 'started_at', 'settings_payload', 'updated_at'])

    def open_question(self, question_index: int, time_limit_seconds: int = 30):
        """Savol ochish: Savolni o'quvchilarga taqdim etish va taymerni yoqish."""
        if self.session.status != self.STATE_ACTIVE:
            raise InvalidStateTransitionError(
                f"Savol ochish faqat 'active' sessiyada mumkin, hozirgi holat: {self.session.status}"
            )
        if self.round_phase not in (self.PHASE_IDLE, self.PHASE_LEADERBOARD, self.PHASE_PREVIEW, self.PHASE_ANSWER_REVEAL):
            raise InvalidStateTransitionError(
                f"Savolni joriy fazadan ochib bo'lmaydi: {self.round_phase}"
            )
        self.session.current_question_index = question_index
        now_ts = timezone.now().timestamp()
        deadline_ts = now_ts + time_limit_seconds
        self.session.settings_payload['current_deadline_ts'] = deadline_ts
        self.session.settings_payload['question_time_limit'] = time_limit_seconds
        self._update_round_phase(self.PHASE_QUESTION_OPEN)
        self.session.save(update_fields=['current_question_index', 'settings_payload', 'updated_at'])
        return deadline_ts

    def close_question(self):
        """Savolni yopish (taymer tugadi yoki o'qituvchi force-close qildi)."""
        if self.session.status != self.STATE_ACTIVE:
            raise InvalidStateTransitionError("Faqat faol sessiyada savolni yopish mumkin.")
        if self.round_phase != self.PHASE_QUESTION_OPEN:
            raise InvalidStateTransitionError(
                f"Faqat ochiq savolni yopish mumkin, joriy faza: {self.round_phase}"
            )
        self._update_round_phase(self.PHASE_QUESTION_CLOSED)
        self.session.save(update_fields=['settings_payload', 'updated_at'])

    def reveal_answer(self):
        """To'g'ri javobni oshkor qilish."""
        if self.session.status != self.STATE_ACTIVE:
            raise InvalidStateTransitionError("Faqat faol sessiyada javoblarni ochish mumkin.")
        if self.round_phase not in (self.PHASE_QUESTION_CLOSED, self.PHASE_QUESTION_OPEN):
            raise InvalidStateTransitionError(
                f"Javoblarni faqat savol yopilgach ochish mumkin, joriy faza: {self.round_phase}"
            )
        self._update_round_phase(self.PHASE_ANSWER_REVEAL)
        self.session.save(update_fields=['settings_payload', 'updated_at'])

    def show_leaderboard(self):
        """Top reytingni ko'rsatish."""
        if self.session.status != self.STATE_ACTIVE:
            raise InvalidStateTransitionError("Faqat faol sessiyada reytingni ko'rsatish mumkin.")
        if self.round_phase not in (self.PHASE_ANSWER_REVEAL, self.PHASE_QUESTION_CLOSED):
            raise InvalidStateTransitionError(
                f"Reytingni faqat javoblar ochilgach ko'rsatish mumkin, joriy faza: {self.round_phase}"
            )
        self._update_round_phase(self.PHASE_LEADERBOARD)
        self.session.save(update_fields=['settings_payload', 'updated_at'])

    def pause(self):
        """Sessiyani pauza qilish (muzlatish)."""
        if self.session.status != self.STATE_ACTIVE:
            raise InvalidStateTransitionError("Faqat faol sessiyani pauza qilish mumkin.")
        self.paused_from_phase = self.round_phase
        self.session.settings_payload['paused_from_phase'] = self.round_phase
        self.session.status = self.STATE_PAUSED
        self.session.save(update_fields=['status', 'settings_payload', 'updated_at'])

    def resume(self):
        """Muzlatilgan sessiyani davom ettirish."""
        if self.session.status != self.STATE_PAUSED:
            raise InvalidStateTransitionError("Faqat pauzadagi sessiyani davom ettirish mumkin.")
        self.session.status = self.STATE_ACTIVE
        resumed_phase = self.session.settings_payload.get('paused_from_phase', self.PHASE_IDLE)
        self._update_round_phase(resumed_phase)
        self.session.settings_payload.pop('paused_from_phase', None)
        self.session.save(update_fields=['status', 'settings_payload', 'updated_at'])

    def show_summary(self):
        """Xulosaviy podium va umumiy natijalar fazasiga o'tish."""
        if self.session.status not in (self.STATE_ACTIVE, self.STATE_PAUSED):
            raise InvalidStateTransitionError("Faqat faol sessiyada natijalarni ko'rsatish mumkin.")
        self._update_round_phase(self.PHASE_SUMMARY)
        self.session.save(update_fields=['settings_payload', 'updated_at'])

    def complete(self):
        """Sessiyani to'liq yakunlash."""
        if self.session.status in (self.STATE_COMPLETED, self.STATE_CANCELLED):
            raise InvalidStateTransitionError(f"Sessiya allaqachon yakunlangan: {self.session.status}")
        self.session.status = self.STATE_COMPLETED
        self.session.ended_at = timezone.now()
        self._update_round_phase(self.PHASE_SUMMARY)
        self.session.save(update_fields=['status', 'ended_at', 'settings_payload', 'updated_at'])

    def cancel(self):
        """Sessiyani bekor qilish."""
        if self.session.status in (self.STATE_COMPLETED, self.STATE_CANCELLED):
            raise InvalidStateTransitionError(f"Sessiya allaqachon yopilgan: {self.session.status}")
        self.session.status = self.STATE_CANCELLED
        self.session.ended_at = timezone.now()
        self.session.save(update_fields=['status', 'ended_at', 'updated_at'])

    def can_participant_join(self) -> bool:
        """Ishtirokchi qo'shilishi mumkinligini tekshiradi."""
        if self.session.status != self.STATE_LOBBY:
            return False
        if self.session.is_lobby_locked:
            return False
        return True

    def _update_round_phase(self, phase: str):
        self.round_phase = phase
        self.session.settings_payload['round_phase'] = phase
