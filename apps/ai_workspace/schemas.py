"""
Structured Output Schemas for AI Generated Quizzes & Questions.
Spetsifikatsiya: .docs/ai/AI_OUTPUT_SCHEMAS.md
"""
from typing import Optional, List, Union, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator


class QuestionTypeEnum(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    ORDERING = "ordering"
    OPEN_SHORT = "open_short"


class DifficultyEnum(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AIGeneratedOption(BaseModel):
    id: str = Field(description="Variant identifikatori: A, B, C yoki D")
    text: str = Field(description="Variant matni (LaTeX formulalar bilan)")


class AIGeneratedQuestion(BaseModel):
    order: int = Field(default=1, ge=1, le=100, description="Tartib raqami")
    prompt: str = Field(min_length=5, description="Savol matni")
    type: str = Field(default="single_choice", description="Savol turi")
    options: List[AIGeneratedOption] = Field(min_length=2, max_length=6, description="Variantlar ro'yxati")
    correct_answer: Union[str, List[str], Dict[str, Any]] = Field(description="To'g'ri javob kaliti")
    accepted_alternatives: Optional[List[str]] = Field(default_factory=list, description="Qo'shimcha to'g'ri variantlar")
    explanation: str = Field(min_length=5, description="Pedagogik tushuntirish va yechim")
    difficulty: str = Field(default="medium", description="Qiyinchilik darajasi")
    time_limit_seconds: int = Field(default=30, ge=5, le=300, description="Vaqt chegarasi")
    points: int = Field(default=1000, ge=100, le=5000, description="Standart ball")
    tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_correct_answer_exists(self):
        """Cross-Field validation: To'g'ri javob variantlar ichida mavjudligi."""
        option_ids = {opt.id for opt in self.options}

        ans = self.correct_answer
        if isinstance(ans, str):
            if ans not in option_ids:
                raise ValueError(f"To'g'ri javob '{ans}' variantlar ichida ({option_ids}) topilmadi!")
        elif isinstance(ans, list):
            for a in ans:
                if str(a) not in option_ids:
                    raise ValueError(f"To'g'ri javob '{a}' variantlar ichida topilmadi!")
        elif isinstance(ans, dict):
            sel_id = ans.get('selected_option_id')
            if sel_id and sel_id not in option_ids:
                raise ValueError(f"To'g'ri javob '{sel_id}' variantlar ichida topilmadi!")
        return self


class AIGeneratedQuiz(BaseModel):
    title: str = Field(min_length=3, max_length=150, description="Viktorina sarlavhasi")
    description: str = Field(default="", max_length=500, description="Qisqacha tavsif")
    subject: str = Field(default="Umumiy", description="Fan nomi")
    grade_level: int = Field(default=7, ge=1, le=11, description="Sinf darajasi")
    language: str = Field(default="uz", description="Til kodi: uz, ru, en")
    suggested_game_mode: str = Field(default="classic", description="Tavsiya etiladigan o'yin rejimi")
    questions: List[AIGeneratedQuestion] = Field(min_length=1, max_length=50, description="Savollar ro'yxati")


class AIQuestionRevisionProposal(BaseModel):
    question_order: int
    change_summary: str = Field(description="Qilingan o'zgarishning qisqa sababi")
    modified_fields: List[str] = Field(description="O'zgargan maydonlar ro'yxati: prompt, options, correct_answer")
    new_question_data: AIGeneratedQuestion


class QuizRequirements(BaseModel):
    subject: str = Field(default="Umumiy")
    grade_level: int = Field(default=7, ge=1, le=11)
    topic: str = Field(min_length=2)
    question_count: int = Field(default=10, ge=1, le=50)
    difficulty: str = Field(default="medium")
    target_game_mode: str = Field(default="classic")
