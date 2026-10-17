"""
EduSelf Game Engine - Base Plugin Architecture.
Spetsifikatsiya: .docs/engine/GAME_PLUGIN_ARCHITECTURE.md
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
    session_id: str
    quiz_id: str = ""
    host_id: str = ""
    current_round: int = 0
    total_rounds: int = 0
    current_question: Optional[Dict[str, Any]] = None
    participants: Dict[str, Any] = field(default_factory=dict)
    teams: Dict[str, Any] = field(default_factory=dict)
    custom_state: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)


class BaseGameModePlugin(ABC):
    """
    Barcha o'yin rejimlari uchun umumiy plagin interfeysi.
    Open-Closed Principle: Yangi rejimlar yadro transport va xavfsizlik
    qismlarini o'zgartirmasdan plagin sifatida ulanadi.
    """
    mode_id: str = ""
    display_name: str = ""
    category: str = "general"
    supported_form_factors: List[FormFactor] = [FormFactor.LIVE]
    settings_schema: Dict[str, Any] = {}

    @abstractmethod
    async def on_session_init(self, context: GameContext) -> None:
        """Sessiya boshlanganda holatni initsializatsiya qilish."""
        pass

    @abstractmethod
    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        """Savol ochilganda o'yin dinamikasiga oid o'zgarishlar."""
        pass

    @abstractmethod
    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        """
        Talaba javob yuborganda chaqiriladi.
        Qaytaradi: {"is_correct": bool, "points_awarded": int, "game_effects": dict}
        """
        pass

    @abstractmethod
    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        """Vaqtga asoslangan animatsiya yoki taymer tiklari uchun."""
        pass

    @abstractmethod
    def check_end_condition(self, context: GameContext) -> bool:
        """O'yin muddatidan oldin yakunlandimi yoki yo'qligini tekshirish."""
        pass

    @abstractmethod
    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        """
        Rol bo'yicha holatni filtrlash:
        'host', 'student', 'projector'
        """
        pass
