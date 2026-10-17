"""
Unit testlar: Pydantic v2 chiqish sxemalari va cross-field validatsiya.
Spetsifikatsiya: .docs/ai/AI_OUTPUT_SCHEMAS.md
"""
import pytest
from pydantic import ValidationError
from apps.ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIGeneratedQuiz,
    AIQuestionRevisionProposal,
    QuizRequirements
)


class TestAIGeneratedSchemas:
    def test_valid_question_schema(self):
        """To'g'ri savol sxemasi validatsiyadan o'tishi kerak."""
        q = AIGeneratedQuestion(
            order=1,
            prompt="Nyutonning birinchi qonuni nima deb ataladi?",
            options=[
                AIGeneratedOption(id="A", text="Inersiya qonuni"),
                AIGeneratedOption(id="B", text="Gravitatsiya qonuni"),
                AIGeneratedOption(id="C", text="Impuls saqlanish qonuni"),
                AIGeneratedOption(id="D", text="Energiya qonuni")
            ],
            correct_answer="A",
            explanation="Nyutonning 1-qonuni inersial sanoq sistemalari va inersiya qonunidir.",
            time_limit_seconds=30,
            points=1000
        )
        assert q.correct_answer == "A"
        assert len(q.options) == 4

    def test_cross_field_validation_invalid_correct_answer(self):
        """To'g'ri javob 'Z' variantlar (A, B, C) ichida bo'lmasa, ValidationError qo'zg'atilishi shart."""
        with pytest.raises(ValidationError, match="variantlar ichida .* topilmadi"):
            AIGeneratedQuestion(
                order=1,
                prompt="Quyosh qayerdan chiqadi?",
                options=[
                    AIGeneratedOption(id="A", text="Sharq"),
                    AIGeneratedOption(id="B", text="G'arb"),
                    AIGeneratedOption(id="C", text="Shimol")
                ],
                correct_answer="Z",  # Mavjud emas!
                explanation="Quyosh sharqdan chiqadi."
            )

    def test_valid_quiz_schema(self):
        """To'liq viktorina sxemasi."""
        quiz = AIGeneratedQuiz(
            title="8-sinf Fizika Zichlik",
            description="Zichlik va massa mavzulari",
            subject="Fizika",
            grade_level=8,
            questions=[
                AIGeneratedQuestion(
                    order=1,
                    prompt="Zichlik formulasini toping:",
                    options=[
                        AIGeneratedOption(id="A", text="$\\rho = m / V$"),
                        AIGeneratedOption(id="B", text="$\\rho = m \\cdot V$")
                    ],
                    correct_answer="A",
                    explanation="Zichlik birlik hajmga to'g'ri keluvchi massa: $\\rho = m / V$."
                )
            ]
        )
        assert quiz.grade_level == 8
        assert len(quiz.questions) == 1
        assert quiz.questions[0].options[0].id == "A"

    def test_quiz_requirements_schema(self):
        """QuizRequirements parametrlar sxemasi."""
        req = QuizRequirements(
            subject="Kimyo",
            grade_level=9,
            topic="Davriy sistema",
            question_count=10
        )
        assert req.subject == "Kimyo"
        assert req.question_count == 10
