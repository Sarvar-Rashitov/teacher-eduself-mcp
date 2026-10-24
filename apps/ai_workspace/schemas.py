from enum import Enum
from typing import Optional, List, Union, Any
from pydantic import BaseModel, Field, model_validator


class QuestionTypeEnum(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_TEXT = "open_short"
    NUMERIC = "numeric"
    ORDERING = "ordering"
    CATEGORIZATION = "categorization"
    CLOZE = "cloze"


class DifficultyEnum(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AIGeneratedOption(BaseModel):
    id: str = Field(..., description="Option key, e.g. 'A', 'B', 'C', 'D' or 'true', 'false'")
    text: str = Field(..., description="Option display text (with LaTeX expressions if math/science)")


class AIGeneratedQuestion(BaseModel):
    order: int = Field(default=1, ge=1, le=100, description="Question sequential order")
    prompt: str = Field(..., min_length=5, description="Question prompt text")
    type: str = Field(default="single_choice", description="Question type identifier")
    options: List[AIGeneratedOption] = Field(default_factory=list, description="Answer options")
    correct_answer: Union[str, List[str], Any] = Field(..., description="Correct option ID or list of IDs")
    accepted_alternatives: Optional[List[str]] = Field(default_factory=list, description="Alternative correct answers")
    explanation: Optional[str] = Field(default="", description="Pedagogical explanation of why this answer is correct")
    difficulty: str = Field(default="medium", description="Difficulty level: easy, medium, hard")
    time_limit_seconds: int = Field(default=30, ge=5, le=300, description="Recommended time limit")
    points: int = Field(default=1000, ge=100, le=5000, description="Point value")
    tags: List[str] = Field(default_factory=list, description="Educational topic tags")
    is_locked: bool = Field(default=False, description="Whether question is locked by teacher from AI modifications")
    media_url: Optional[str] = Field(default=None, description="Optional image/media URL for question")
    media_type: Optional[str] = Field(default=None, description="Media type (e.g. image)")

    @model_validator(mode="after")
    def validate_correct_answer_exists(self):
        """
        DOC-71 & DOC-74: Cross-field validation ensuring correct answer exists
        within provided options for single choice, multiple choice, and true/false.
        """
        if self.options and self.type in ("single_choice", "true_false", "multiple_choice"):
            option_ids = {opt.id for opt in self.options}
            if isinstance(self.correct_answer, str):
                if self.correct_answer not in option_ids:
                    raise ValueError(
                        f"Correct answer '{self.correct_answer}' not found in options {option_ids}"
                    )
            elif isinstance(self.correct_answer, list):
                for ans in self.correct_answer:
                    if str(ans) not in option_ids:
                        raise ValueError(
                            f"Correct answer '{ans}' not found in options {option_ids}"
                        )
        return self


class AIGeneratedQuiz(BaseModel):
    """
    DOC-71 Section 2: Complete quiz schema returned by AI generation.
    """
    title: str = Field(..., min_length=3, max_length=150, description="Quiz title")
    description: Optional[str] = Field(default="", max_length=500, description="Short pedagogical description")
    subject: str = Field(..., description="Subject domain (e.g. Fizika, Kimyo, Matematika)")
    grade_level: int = Field(default=7, ge=1, le=11, description="School grade level (1 to 11)")
    language: str = Field(default="uz", description="Language code: uz, ru, en")
    suggested_game_mode: str = Field(default="classic", description="Suggested game mode")
    questions: List[AIGeneratedQuestion] = Field(..., min_length=1, max_length=100, description="Questions list")


class AIQuestionRevisionProposal(BaseModel):
    """
    DOC-71 Section 3: Revision proposal for a specific question.
    Presented to teacher in Before / After side-by-side diff view.
    """
    question_order: int = Field(..., description="Target question order index")
    change_summary: str = Field(..., description="Short explanation of why and what was changed")
    modified_fields: List[str] = Field(default_factory=list, description="List of modified field names")
    new_question_data: AIGeneratedQuestion = Field(..., description="Revised question structure")


class GenerateQuizRequest(BaseModel):
    """Payload sent by teacher to request a new quiz generation."""
    topic: Optional[str] = None
    subject: Optional[str] = None
    grade_level: int = Field(default=7, ge=1, le=11)
    question_count: int = Field(default=5, ge=1, le=100)
    language: str = Field(default="uz")
    game_mode: str = Field(default="classic")
    text_content: Optional[str] = None
    prompt: Optional[str] = None
    custom_instructions: Optional[str] = None
    preferred_provider: Optional[str] = None
