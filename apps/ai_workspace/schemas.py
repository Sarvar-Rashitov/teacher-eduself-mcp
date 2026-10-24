from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionTypeEnum(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    ORDERING = "ordering"
    CATEGORIZATION = "categorization"
    CLOZE = "cloze"
    OPEN_SHORT = "open_short"


class DifficultyEnum(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


FORBIDDEN_OPTION_PHRASES = [
    "barchasi to'g'ri",
    "barchasi to‘g‘ri",
    "barcha javoblar to'g'ri",
    "hammasi to'g'ri",
    "yuqoridagilarning barchasi",
    "hech biri to'g'ri emas",
    "hech qaysi biri",
    "a va b javoblar",
    "all of the above",
    "none of the above",
    "все вышеперечисленное",
    "ни один из вышеперечисленных",
]


class AIGeneratedOption(BaseModel):
    id: str = Field(description="Option identifier: A, B, C, D or UUID")
    text: str = Field(description="Option text, LaTeX allowed ($...$)")


class AIGeneratedQuestion(BaseModel):
    order: int = Field(default=1, ge=1, le=100, description="Sequential question order")
    prompt: str = Field(min_length=5, description="Question prompt text")
    type: QuestionTypeEnum = Field(default=QuestionTypeEnum.SINGLE_CHOICE)
    options: List[AIGeneratedOption] = Field(default_factory=list, description="Answer options")
    correct_answer: Union[str, List[str], Dict[str, Any]] = Field(description="Correct option ID(s) or payload")
    accepted_alternatives: Optional[List[str]] = Field(default_factory=list)
    explanation: str = Field(default="", description="Pedagogical explanation of the correct solution")
    difficulty: DifficultyEnum = Field(default=DifficultyEnum.MEDIUM)
    time_limit_seconds: int = Field(default=30, ge=5, le=300)
    points: int = Field(default=1000, ge=100, le=5000)
    tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_options_and_correct_answer(self) -> "AIGeneratedQuestion":
        # Choice-based questions must have options
        if self.type in (QuestionTypeEnum.SINGLE_CHOICE, QuestionTypeEnum.MULTIPLE_CHOICE, QuestionTypeEnum.TRUE_FALSE):
            if len(self.options) < 2:
                raise ValueError(f"Question type '{self.type.value}' must provide at least 2 options.")

            option_ids = {opt.id for opt in self.options}
            option_texts = [opt.text.strip().lower() for opt in self.options]

            # 1. No duplicate options
            if len(option_texts) != len(set(option_texts)):
                raise ValueError("Duplicate option text detected in question options.")

            # 2. No forbidden option phrases (shuffle breaking)
            for text in option_texts:
                for forbidden in FORBIDDEN_OPTION_PHRASES:
                    if forbidden in text:
                        raise ValueError(f"Forbidden option phrase detected: '{forbidden}' is prohibited.")

            # 3. Correct answer integrity check
            if isinstance(self.correct_answer, str):
                if self.correct_answer not in option_ids:
                    # Allow true/false textual mapping if options have matching id or text
                    if self.type == QuestionTypeEnum.TRUE_FALSE:
                        matched = any(opt.text.strip().lower() == self.correct_answer.strip().lower() for opt in self.options)
                        if not matched:
                            raise ValueError(f"Correct answer '{self.correct_answer}' not in option IDs {option_ids}.")
                    else:
                        raise ValueError(f"Correct answer '{self.correct_answer}' not in option IDs {option_ids}.")
            elif isinstance(self.correct_answer, list):
                for ans_id in self.correct_answer:
                    if str(ans_id) not in option_ids:
                        raise ValueError(f"Correct answer ID '{ans_id}' not found in options {option_ids}.")
            elif isinstance(self.correct_answer, dict):
                # E.g. {"correct_option_id": "A"}
                c_id = self.correct_answer.get("correct_option_id") or self.correct_answer.get("correct_option_ids")
                if isinstance(c_id, str) and c_id not in option_ids:
                    raise ValueError(f"Correct answer ID '{c_id}' not found in options {option_ids}.")

        return self


class AIGeneratedQuiz(BaseModel):
    title: str = Field(min_length=3, max_length=150, description="Quiz title")
    description: str = Field(default="", max_length=500, description="Brief description")
    subject: str = Field(default="Umumiy", description="Subject name")
    grade_level: int = Field(default=7, ge=1, le=11, description="Grade level (1-11)")
    language: str = Field(default="uz", description="Language code: uz, ru, en")
    suggested_game_mode: str = Field(default="classic", description="Suggested classroom game mode")
    questions: List[AIGeneratedQuestion] = Field(min_length=1, max_length=50, description="Generated questions")


class AIQuestionRevisionProposal(BaseModel):
    question_order: int = Field(description="Order of question being revised")
    change_summary: str = Field(description="Reason and brief summary of the proposed change")
    modified_fields: List[str] = Field(default_factory=list, description="Fields changed: prompt, options, etc.")
    original_question_data: Dict[str, Any] = Field(default_factory=dict, description="Previous question state")
    new_question_data: AIGeneratedQuestion = Field(description="Proposed new question state")
