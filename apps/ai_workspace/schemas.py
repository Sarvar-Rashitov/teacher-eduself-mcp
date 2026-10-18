"""
Strict Pydantic v2 Output Schemas for AI Quiz Generation and Question Revision.
Enforces type safety, cross-field integrity, and pedagogical constraints.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, model_validator


class QuestionTypeEnum(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_SELECT = "multiple_select"
    TRUE_FALSE = "true_false"
    SHORT_TEXT = "short_text"
    NUMERIC = "numeric"
    PUZZLE_ORDER = "puzzle_order"


class DifficultyEnum(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


FORBIDDEN_OPTION_PATTERNS = [
    "barchasi to'g'ri",
    "barchasi to‘g‘ri",
    "yuqoridagilarning barchasi",
    "hech biri to'g'ri emas",
    "hech biri to‘g‘ri emas",
    "hech biri emas",
    "all of the above",
    "none of the above",
    "все вышеперечисленное",
    "ни один из вышеперечисленных",
]


class AIGeneratedOption(BaseModel):
    id: str = Field(description="Option identifier: A, B, C, D, etc.")
    text: str = Field(description="Option text, supporting LaTeX expressions via $...$")

    @model_validator(mode="after")
    def validate_forbidden_phrases(self):
        clean_text = self.text.strip().lower()
        for forbidden in FORBIDDEN_OPTION_PATTERNS:
            if forbidden in clean_text:
                raise ValueError(
                    f"Option '{self.id}' contains forbidden ambiguous pattern: '{forbidden}'."
                )
        return self


class AIGeneratedQuestion(BaseModel):
    order: int = Field(ge=1, le=100, description="1-based question order in the quiz")
    prompt: str = Field(min_length=5, description="Question prompt / task text")
    type: QuestionTypeEnum = Field(default=QuestionTypeEnum.SINGLE_CHOICE)
    options: List[AIGeneratedOption] = Field(min_length=2, max_length=6)
    correct_answer: Union[str, List[str]] = Field(description="Correct option ID or list of IDs")
    accepted_alternatives: Optional[List[str]] = Field(default_factory=list)
    explanation: str = Field(default="", description="Pedagogical explanation of why the answer is correct")
    difficulty: DifficultyEnum = Field(default=DifficultyEnum.MEDIUM)
    time_limit_seconds: int = Field(default=30, ge=5, le=300)
    points: int = Field(default=1000, ge=100, le=5000)
    tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_correct_answer_exists(self):
        option_ids = {opt.id for opt in self.options}
        if isinstance(self.correct_answer, str):
            if self.correct_answer not in option_ids:
                raise ValueError(
                    f"Correct answer '{self.correct_answer}' not found in options ({option_ids})."
                )
        elif isinstance(self.correct_answer, list):
            if not self.correct_answer:
                raise ValueError("Correct answer list cannot be empty.")
            for ans in self.correct_answer:
                if ans not in option_ids:
                    raise ValueError(f"Correct answer '{ans}' not found in options ({option_ids}).")

        # Verify duplicate option texts
        texts = [opt.text.strip().lower() for opt in self.options]
        if len(texts) != len(set(texts)):
            raise ValueError(f"Question {self.order} has duplicate option texts.")

        return self


class AIGeneratedQuiz(BaseModel):
    title: str = Field(min_length=3, max_length=150, description="Quiz title")
    description: str = Field(default="", max_length=500, description="Short summary/description")
    subject: str = Field(description="Subject name (e.g. Fizika, Kimyo, Matematika)")
    grade_level: int = Field(ge=1, le=11, description="Target school grade (1-11)")
    language: str = Field(default="uz", description="Locale code: uz, ru, en")
    suggested_game_mode: str = Field(default="classic", description="Suggested live session game mode")
    questions: List[AIGeneratedQuestion] = Field(min_length=1, max_length=50)


class AIQuestionRevisionProposal(BaseModel):
    question_order: int
    change_summary: str = Field(description="Brief explanation of what was changed and why")
    modified_fields: List[str] = Field(description="List of fields changed: prompt, options, correct_answer, explanation")
    new_question_data: AIGeneratedQuestion


class QuizRequirements(BaseModel):
    subject: str
    grade_level: int = Field(ge=1, le=11)
    topic: str
    question_count: int = Field(default=10, ge=1, le=50)
    difficulty: DifficultyEnum = Field(default=DifficultyEnum.MEDIUM)
    target_game_mode: str = Field(default="classic")
    language: str = Field(default="uz")
