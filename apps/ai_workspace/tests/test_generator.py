import asyncio
import pytest
from unittest.mock import AsyncMock

from apps.ai_workspace.generator import AIQuizGenerator
from apps.ai_workspace.schemas import (
    GenerateQuizRequest,
    AIGeneratedQuiz,
    AIGeneratedQuestion,
    AIGeneratedOption,
    AIQuestionRevisionProposal,
)
from apps.ai_workspace.diff_engine import AIDiffEngine


class TestAIQuizGenerator:
    def test_generate_quiz_success(self):
        async def _run():
            mock_quiz = AIGeneratedQuiz(
                title="Fizika 7-sinf",
                subject="Fizika",
                grade_level=7,
                questions=[
                    AIGeneratedQuestion(
                        order=1,
                        prompt="Tezlik birligi nima?",
                        type="single_choice",
                        options=[
                            AIGeneratedOption(id="A", text="m/s"),
                            AIGeneratedOption(id="B", text="kg"),
                        ],
                        correct_answer="A",
                    )
                ],
            )

            mock_router = AsyncMock()
            mock_router.execute_structured.return_value = mock_quiz

            generator = AIQuizGenerator(router=mock_router)
            req = GenerateQuizRequest(
                topic="Tezlik",
                subject="Fizika",
                grade_level=7,
                question_count=1,
            )

            result = await generator.generate_quiz(req)
            assert result.title == "Fizika 7-sinf"
            assert len(result.questions) == 1
            assert result.questions[0].correct_answer == "A"
            assert mock_router.execute_structured.call_count == 1

        asyncio.run(_run())

    def test_generate_quiz_with_custom_teacher_prompt(self):
        async def _run():
            mock_quiz = AIGeneratedQuiz(
                title="Kimyo Maxsus Test",
                subject="Kimyo",
                grade_level=8,
                questions=[
                    AIGeneratedQuestion(
                        order=1,
                        prompt="D.I. Mendeleyev qaysi elementni kashf qilgan?",
                        type="single_choice",
                        options=[
                            AIGeneratedOption(id="A", text="Davriy qonun"),
                            AIGeneratedOption(id="B", text="Kislorod"),
                        ],
                        correct_answer="A",
                    )
                ],
            )

            mock_router = AsyncMock()
            mock_router.execute_structured.return_value = mock_quiz

            generator = AIQuizGenerator(router=mock_router)
            req = GenerateQuizRequest(
                topic="Davriy jadval",
                subject="Kimyo",
                grade_level=8,
                question_count=20,
                prompt="Faqat 1-guruh ishqoriy metallari bo'yicha tuzilsin",
            )

            result = await generator.generate_quiz(req)
            assert result.title == "Kimyo Maxsus Test"
            # Verify custom prompt was incorporated in messages passed to execute_structured
            call_kwargs = mock_router.execute_structured.call_args.kwargs
            messages = call_kwargs["messages"]
            assert any("Faqat 1-guruh ishqoriy metallari bo'yicha tuzilsin" in m["content"] for m in messages)
            # Verify dynamic config was passed
            assert call_kwargs["config"].max_tokens >= 7000

        asyncio.run(_run())

    def test_pedagogical_fallback_generates_large_batches(self):
        generator = AIQuizGenerator()
        req = GenerateQuizRequest(
            topic="Kosmik Fazoviy Parvozlar",
            subject="Astronomiya",
            grade_level=10,
            question_count=30,
            prompt="Quyosh tizimi va sayyoralar parvozi",
        )
        quiz = generator._generate_intelligent_pedagogical_quiz(req)
        assert len(quiz.questions) == 30
        # Zero duplication check
        prompts = [q.prompt for q in quiz.questions]
        assert len(prompts) == len(set(prompts))

    def test_revise_question_and_lock_protection(self):
        async def _run():
            mock_router = AsyncMock()
            mock_proposal = AIQuestionRevisionProposal(
                question_order=1,
                change_summary="Variantlar osonlashtirildi",
                modified_fields=["options"],
                new_question_data=AIGeneratedQuestion(
                    order=1,
                    prompt="Tezlik formulasi qaysi?",
                    type="single_choice",
                    options=[
                        AIGeneratedOption(id="A", text="v = s / t"),
                        AIGeneratedOption(id="B", text="v = m * a"),
                    ],
                    correct_answer="A",
                ),
            )
            mock_router.execute_structured.return_value = mock_proposal
            generator = AIQuizGenerator(router=mock_router)

            # 1. Normal unlocked question revision
            unlocked_q = {
                "order": 1,
                "prompt": "Tezlik?",
                "is_locked": False,
            }
            proposal = await generator.revise_question(unlocked_q, "Osonroq variant ber")
            assert proposal.change_summary == "Variantlar osonlashtirildi"
            assert proposal.new_question_data.correct_answer == "A"

            # 2. Locked question revision MUST raise ValueError
            locked_q = {
                "order": 2,
                "prompt": "Qulflangan savol",
                "is_locked": True,
            }
            with pytest.raises(ValueError) as exc_info:
                await generator.revise_question(locked_q, "O'zgartir")
            assert "Qulflangan" in str(exc_info.value)

        asyncio.run(_run())


class TestAIDiffEngine:
    def test_compute_diff_add_modify_remove(self):
        orig = [
            {"order": 1, "prompt": "Savol 1", "correct_answer": "A", "is_locked": False},
            {"order": 2, "prompt": "Savol 2 (Qulflangan)", "correct_answer": "B", "is_locked": True},
            {"order": 3, "prompt": "Savol 3", "correct_answer": "C", "is_locked": False},
        ]
        prop = [
            {"order": 1, "prompt": "Savol 1 (Tahrirlangan)", "correct_answer": "A", "is_locked": False},
            # order 2 omitted by proposed (attempted delete of locked question)
            {"order": 3, "prompt": "Savol 3", "correct_answer": "C", "is_locked": False},
            {"order": 4, "prompt": "Yangi Savol 4", "correct_answer": "D", "is_locked": False},
        ]

        diff = AIDiffEngine.compute_diff(orig, prop)

        # Added: order 4
        assert len(diff["added"]) == 1
        assert diff["added"][0]["order"] == 4

        # Modified: order 1
        assert len(diff["modified"]) == 1
        assert diff["modified"][0]["order"] == 1

        # Unchanged: order 3 and blocked locked order 2
        assert len(diff["unchanged"]) == 2

        # Blocked: order 2 deletion was blocked
        assert len(diff["blocked_modifications"]) == 1
        assert diff["blocked_modifications"][0]["order"] == 2

    def test_apply_diff_strictly_preserves_locked_question(self):
        orig = [
            {"order": 1, "prompt": "Savol 1 (O'zgartiriladigan)", "is_locked": False},
            {"order": 2, "prompt": "Savol 2 (Qat'iy Qulflangan)", "is_locked": True},
        ]
        # Proposed changes both 1 and tries to overwrite 2
        prop = [
            {"order": 1, "prompt": "Savol 1 (Yangi matn)", "is_locked": False},
            {"order": 2, "prompt": "Savol 2 (Buzilgan matn)", "is_locked": False},
        ]

        merged = AIDiffEngine.apply_diff(orig, prop)

        assert len(merged) == 2
        # Order 1 was updated
        assert merged[0]["prompt"] == "Savol 1 (Yangi matn)"
        # Order 2 was strictly preserved as original
        assert merged[1]["prompt"] == "Savol 2 (Qat'iy Qulflangan)"
        assert merged[1]["is_locked"] is True
