"""
Base Game Mode Plugin Contract and Context Definitions.
Defines BaseGameMode, GameContext, and FormFactor based on GAME_PLUGIN_ARCHITECTURE.md.
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum


class FormFactor(str, Enum):
    LIVE = "live"
    TEAM = "team"
    SOLO = "solo"
    HOMEWORK = "homework"


@dataclass
class GameContext:
    """
    O'yin davomidagi umumiy kontekst va parametrlar.
    """
    session_id: str
    quiz_id: str
    host_id: str
    current_round: int = 0
    total_rounds: int = 0
    current_question: Optional[Dict[str, Any]] = None
    participants: Dict[str, Any] = field(default_factory=dict)
    teams: Dict[str, Any] = field(default_factory=dict)
    custom_state: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)


class BaseGameMode(ABC):
    """
    Barcha o'yin rejimlari uchun umumiy abstrakt interfeys (Open-Closed Principle).
    Har bir rejim transport, saqlash va hisobotlarga bog'liq bo'lmagan holda ishlaydi.
    """
    mode_id: str
    display_name: str
    category: str = "Classic"
    supported_form_factors: List[FormFactor] = [FormFactor.LIVE]
    settings_schema: Dict[str, Any] = {}

    @abstractmethod
    def on_session_init(self, context: GameContext) -> None:
        """Sessiya boshlanayotganda rejimga xos dastlabki holatni o'rnatish."""
        pass

    @abstractmethod
    def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        """Yangi savol ochilganda o'yin dinamikasiga oid o'zgarishlar."""
        pass

    @abstractmethod
    def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        """
        Talaba javob yuborganida chaqiriladi.
        Qaytaradi: {"is_correct": bool, "points_awarded": int, "effects": dict}
        """
        pass

    def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        """1 soniyalik davriy hodisalar uchun (agar rejimga taymer kerak bo'lsa)."""
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        """O'yin muddatidan oldin yakunlanganligini tekshirish."""
        return False

    @abstractmethod
    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        """
        Rol bo'yicha ma'lumotlarni filtrlash:
        - 'host': O'qituvchi boshqaruv paneli
        - 'student': Talaba mobil ekrani
        - 'projector': Katta ekran
        """
        pass
