"""
Quiz and Question Data Transfer Objects.
Contract between Quiz Engine (Dev 2) and Real-Time WebSocket Engine (Dev 3).
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionDTO:
    id: str
    type: str
    prompt: str
    options: List[Dict[str, Any]]
    correct_answer: Any
    points: int = 1000
    time_limit_seconds: int = 30
    explanation: Optional[str] = None


@dataclass(frozen=True)
class QuizDTO:
    id: str
    title: str
    questions: List[QuestionDTO]
    subject: str = "General"
    grade_level: int = 7
    locale: str = "uz-Latn"
