from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FormFactor(str, Enum):
    LIVE = "live"
    TEAM = "team"
    SOLO = "solo"
    HOMEWORK = "homework"


@dataclass
class GameContext:
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
    Abstract Base Class for all EduSelf Game Modes.
    Implements DOC-63 (GAME_PLUGIN_ARCHITECTURE.md):
    Enforces the Open-Closed Principle allowing new games to be added without
    modifying WebSocket transport, storage, or session lifecycle.
    """

    mode_id: str = "base"
    display_name: str = "Base Game Mode"
    category: str = "general"
    supported_form_factors: List[FormFactor] = [FormFactor.LIVE]
    settings_schema: Dict[str, Any] = {}

    @abstractmethod
    async def on_session_init(self, context: GameContext) -> None:
        """Initializes game-specific state when session is created or started."""
        pass

    @abstractmethod
    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        """Invoked when a new question round opens for students."""
        pass

    @abstractmethod
    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        """
        Processes answer submission.
        Must return:
        {
            "is_correct": bool,
            "points_awarded": int,
            "game_effects": dict
        }
        """
        pass

    @abstractmethod
    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        """Periodic real-time tick (e.g. 1-second interval) for dynamic modes."""
        pass

    @abstractmethod
    def check_end_condition(self, context: GameContext) -> bool:
        """Returns True if the game has ended (e.g. all rounds complete, boss defeated, etc.)."""
        pass

    @abstractmethod
    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        """Filters and serializes context state according to role: 'host', 'student', 'projector'."""
        pass
