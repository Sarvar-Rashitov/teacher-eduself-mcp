"""
Scoring and Answer Submission Data Transfer Objects & Protocols.
Contract between Real-Time WebSocket Engine (Dev 3) and Game Engine / Leaderboard (Dev 4).
"""

from typing import Protocol, Any, runtime_checkable
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerSubmissionDTO:
    participant_id: str
    question_id: str
    user_answer: Any
    time_taken_ms: int
    streak_count: int = 0


@runtime_checkable
class ScoringEngineProtocol(Protocol):
    """Protocol defining score calculation interface."""

    def calculate_score(self, submission: AnswerSubmissionDTO, question: Any) -> int:
        """
        Calculate score (0 to 1500) based on answer correctness, response time, and streak.
        """
        ...
