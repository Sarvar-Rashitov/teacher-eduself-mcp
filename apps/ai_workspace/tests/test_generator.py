import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from ai_workspace.generator import AIQuizGenerator
from ai_workspace.schemas import (
    AIGeneratedQuiz,
    AIGeneratedQuestion,
    AIGeneratedOption,
    AIQuestionRevisionProposal,
    QuestionTypeEnum,
)


@pytest.mark.asyncio
class TestAIQuizGenerator:
    async def test_generate_quiz_success(self):
        mock_router = MagicMock()
        mock_quiz = AIGeneratedQuiz(
            title="Biologiya 8-sinf",
            description="Hujayra tuzilishi mavzusida test",
            subject="Biologiya",
            grade_level=8,
            language="uz",
            questions=[
                AIGeneratedQuestion(
                    order=1,
                    prompt="Hujayraning energetik stansiyasi qaysi organoid?",
                    type=QuestionTypeEnum.SINGLE_CHOICE,
                    options=[
                        AIGeneratedOption(id="A", text="Ribosoma"),
                        AIGeneratedOption(id="B", text="Mitoxondriya"),
                        AIGeneratedOption(id="C", text="Lizosoma"),
                        AIGeneratedOption(id="D", text="Vakuola"),
                    ],
                    correct_answer="B",
                    explanation="Mitoxondriyalar ATF sintez qiladi.",
                )
            ],
        )
        mock_router.generate_structured = AsyncMock(return_value=mock_quiz)

        generator = AIQuizGenerator(router=mock_router)
        result = await generator.generate_quiz(
            topic="Hujayra tuzilishi",
            grade_level=8,
            subject="Biologiya",
            question_count=1,
        )

        assert isinstance(result, AIGeneratedQuiz)
        assert result.title == "Biologiya 8-sinf"
        assert len(result.questions) == 1
        assert result.questions[0].correct_answer == "B"
        assert mock_router.generate_structured.call_count == 1

    async def test_self_healing_recovers_from_validation_error(self):
        mock_router = MagicMock()

        # Attempt 1: Faulty payload with forbidden phrase
        faulty_data = {
            "title": "Fizika Test",
            "description": "Nyuton qonunlari",
            "subject": "Fizika",
            "grade_level": 9,
            "language": "uz",
            "suggested_game_mode": "classic",
            "questions": [
                {
                    "order": 1,
                    "prompt": "Kuch nima?",
                    "type": "single_choice",
                    "options": [
                        {"id": "A", "text": "Jism tezlanishi sababi"},
                        {"id": "B", "text": "Gravitatsiya"},
                        {"id": "C", "text": "Massaning o'zgarishi"},
                        {"id": "D", "text": "Barchasi to'g'ri"},  # Forbidden phrase!
                    ],
                    "correct_answer": "D",
                    "explanation": "Izoh",
                    "difficulty": "medium",
                    "time_limit_seconds": 30,
                    "points": 1000,
                }
            ],
        }

        # Attempt 2: Repaired payload
        healed_data = {
            "title": "Fizika Test",
            "description": "Nyuton qonunlari",
            "subject": "Fizika",
            "grade_level": 9,
            "language": "uz",
            "suggested_game_mode": "classic",
            "questions": [
                {
                    "order": 1,
                    "prompt": "Kuch nima?",
                    "type": "single_choice",
                    "options": [
                        {"id": "A", "text": "Jismlarning o'zaro ta'siri o'lchovi"},
                        {"id": "B", "text": "Jismning inertligi"},
                        {"id": "C", "text": "Harakat trayektoriyasi"},
                        {"id": "D", "text": "Vaqt birligi"},
                    ],
                    "correct_answer": "A",
                    "explanation": "Kuch - bu jismlarning o'zaro ta'sirini ifodalovchi vektor kattalik.",
                    "difficulty": "medium",
                    "time_limit_seconds": 30,
                    "points": 1000,
                }
            ],
        }

        mock_router.generate_structured = AsyncMock(side_effect=[faulty_data, healed_data])

        generator = AIQuizGenerator(router=mock_router, max_healing_retries=2)
        result = await generator.generate_quiz(
            topic="Nyuton qonunlari",
            grade_level=9,
            subject="Fizika",
        )

        assert isinstance(result, AIGeneratedQuiz)
        assert result.questions[0].correct_answer == "A"
        assert result.questions[0].options[3].text == "Vaqt birligi"
        # Must have been called twice (1 initial + 1 healing retry)
        assert mock_router.generate_structured.call_count == 2

    async def test_self_healing_fails_when_retries_exhausted(self):
        mock_router = MagicMock()

        # Both attempts invalid (missing options)
        faulty_data = {
            "title": "Test",
            "questions": [
                {
                    "order": 1,
                    "prompt": "Qisqa",
                    "type": "single_choice",
                    "options": [{"id": "A", "text": "Faqat bitta variant"}],
                    "correct_answer": "A",
                }
            ],
        }

        mock_router.generate_structured = AsyncMock(return_value=faulty_data)

        generator = AIQuizGenerator(router=mock_router, max_healing_retries=2)
        with pytest.raises(ValueError) as exc_info:
            await generator.generate_quiz(topic="Matematika", grade_level=5)

        assert "Validation failed after 2 self-healing attempts" in str(exc_info.value)
        # Attempt 0, Attempt 1, Attempt 2 -> 3 total calls
        assert mock_router.generate_structured.call_count == 3

    async def test_revise_single_question_success(self):
        mock_router = MagicMock()
        mock_proposal = AIQuestionRevisionProposal(
            question_order=1,
            change_summary="Variantlar murakkablashtirildi",
            modified_fields=["options", "correct_answer"],
            original_question_data={"prompt": "2 + 2 = ?"},
            new_question_data=AIGeneratedQuestion(
                order=1,
                prompt="$\\sqrt{16}$ qiymatini toping",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="2"),
                    AIGeneratedOption(id="B", text="4"),
                    AIGeneratedOption(id="C", text="8"),
                    AIGeneratedOption(id="D", text="16"),
                ],
                correct_answer="B",
                explanation="$\\sqrt{16} = 4$",
            ),
        )
        mock_router.generate_structured = AsyncMock(return_value=mock_proposal)

        generator = AIQuizGenerator(router=mock_router)
        res = await generator.revise_single_question(
            original_question={"prompt": "2 + 2 = ?"},
            revision_instruction="Savolni qiyinroq qilib, ildizli formula qo'shing",
            subject="Matematika",
        )

        assert isinstance(res, AIQuestionRevisionProposal)
        assert res.new_question_data.correct_answer == "B"
        assert res.change_summary == "Variantlar murakkablashtirildi"
