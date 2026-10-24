from abc import ABC, abstractmethod
from typing import Optional, Any
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
    quiz_id: str
    host_id: str
    current_round: int = 0
    total_rounds: int = 0
    current_question: Optional[dict[str, Any]] = None
    participants: dict[str, Any] = field(default_factory=dict)
    teams: dict[str, Any] = field(default_factory=dict)
    custom_state: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)


class BaseGameMode(ABC):
    """
    Abstract base class for all pluggable game modes in EduSelf.
    Adheres to Open-Closed Principle (DOC-63).
    """

    mode_id: str
    display_name: str
    category: str
    supported_form_factors: list[FormFactor] = [FormFactor.LIVE]
    settings_schema: dict[str, Any] = {}

    @abstractmethod
    async def on_session_init(self, context: GameContext) -> None:
        """Initializes game-specific state when session starts."""
        pass

    @abstractmethod
    async def on_question_opened(self, question: dict[str, Any], context: GameContext) -> None:
        """Invoked when a new question is opened for responses."""
        pass

    @abstractmethod
    async def on_answer_submitted(self, answer: dict[str, Any], context: GameContext) -> dict[str, Any]:
        """
        Invoked when a participant submits an answer.
        Returns dict with: is_correct, points_awarded, game_effects, etc.
        """
        pass

    @abstractmethod
    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[dict[str, Any]]:
        """Periodic tick loop callback (e.g. 1-second ticks)."""
        pass

    @abstractmethod
    def check_end_condition(self, context: GameContext) -> bool:
        """Determines if the game has reached an early termination condition."""
        pass

    @abstractmethod
    def serialize_state_for_role(self, role: str, context: GameContext) -> dict[str, Any]:
        """
        Serializes custom game mode state filtered by client role:
        'host', 'student', 'projector'.
        """
        pass


BaseGameModePlugin = BaseGameMode
