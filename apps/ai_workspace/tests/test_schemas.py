import pytest
from pydantic import ValidationError
from apps.ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIGeneratedQuiz,
    AIQuestionRevisionProposal,
)
from apps.ai_workspace.tools import validate_quiz_content, suggest_game_modes


class TestAISchemas:
    def test_valid_single_choice_question(self):
        q = AIGeneratedQuestion(
            order=1,
            prompt="Nyutonning birinchi qonuni nima deb ataladi?",
            type="single_choice",
            options=[
                AIGeneratedOption(id="A", text="Inersiya qonuni"),
                AIGeneratedOption(id="B", text="Gravitatsiya qonuni"),
                AIGeneratedOption(id="C", text="Kuch qonuni"),
                AIGeneratedOption(id="D", text="Energiya saqlanish qonuni"),
            ],
            correct_answer="A",
            explanation="Nyutonning 1-qonuni inersiya qonuni deb yuritiladi.",
        )
        assert q.order == 1
        assert q.correct_answer == "A"

    def test_invalid_correct_answer_not_in_options(self):
        with pytest.raises(ValidationError) as exc_info:
            AIGeneratedQuestion(
                order=1,
                prompt="Kislorod davriy jadvalda nechanchi o'rinda?",
                type="single_choice",
                options=[
                    AIGeneratedOption(id="A", text="6"),
                    AIGeneratedOption(id="B", text="7"),
                    AIGeneratedOption(id="C", text="8"),
                ],
                correct_answer="Z",  # Does not exist in options
            )
        assert "not found in options" in str(exc_info.value)

    def test_valid_multiple_choice_question(self):
        q = AIGeneratedQuestion(
            order=2,
            prompt="Quyidagilardan qaysilari inert gazlar hisoblanadi?",
            type="multiple_choice",
            options=[
                AIGeneratedOption(id="A", text="Geliy"),
                AIGeneratedOption(id="B", text="Kislorod"),
                AIGeneratedOption(id="C", text="Neon"),
                AIGeneratedOption(id="D", text="Vodorod"),
            ],
            correct_answer=["A", "C"],
        )
        assert q.correct_answer == ["A", "C"]

    def test_valid_complete_quiz(self):
        quiz = AIGeneratedQuiz(
            title="Kimyo Asoslari",
            description="8-sinf kimyo fanidan boshlang'ich tushunchalar",
            subject="Kimyo",
            grade_level=8,
            language="uz",
            questions=[
                AIGeneratedQuestion(
                    order=1,
                    prompt="Suvning kimyoviy formulasi qaysi?",
                    type="single_choice",
                    options=[
                        AIGeneratedOption(id="A", text="$H_2O$"),
                        AIGeneratedOption(id="B", text="$CO_2$"),
                    ],
                    correct_answer="A",
                )
            ],
        )
        assert quiz.title == "Kimyo Asoslari"
        assert quiz.grade_level == 8
        assert len(quiz.questions) == 1


class TestContentValidationHeuristics:
    def test_duplicate_options_detected(self):
        quiz_data = {
            "questions": [
                {
                    "prompt": "O'zbekiston poytaxti qaysi?",
                    "type": "single_choice",
                    "options": [
                        {"id": "A", "text": "Toshkent"},
                        {"id": "B", "text": "Samarqand"},
                        {"id": "C", "text": "Toshkent"},  # Duplicate
                    ],
                    "correct_answer": "A",
                }
            ]
        }
        report = validate_quiz_content(quiz_data)
        assert report["is_valid"] is False
        assert any("takrorlanish" in err for err in report["errors"])

    def test_forbidden_phrases_detected(self):
        quiz_data = {
            "questions": [
                {
                    "prompt": "Quyidagi javoblarning qaysi biri to'g'ri?",
                    "type": "single_choice",
                    "options": [
                        {"id": "A", "text": "Variant 1"},
                        {"id": "B", "text": "Variant 2"},
                        {"id": "C", "text": "Barchasi to'g'ri"},  # Forbidden phrase
                    ],
                    "correct_answer": "C",
                }
            ]
        }
        report = validate_quiz_content(quiz_data)
        assert report["is_valid"] is False
        assert any("Taqiqlangan variant iborasi" in err for err in report["errors"])

    def test_suggest_game_modes(self):
        suggestions = suggest_game_modes(student_count=25, duration_minutes=15)
        mode_ids = [s["mode_id"] for s in suggestions]
        assert "team_battle" in mode_ids
        assert "gold_quest" in mode_ids
        assert "classic" in mode_ids

    def test_generate_quiz_request_custom_prompt_and_large_limit(self):
        from apps.ai_workspace.schemas import GenerateQuizRequest
        req = GenerateQuizRequest(
            topic="Biologiya",
            subject="Biologiya",
            grade_level=9,
            question_count=50,
            prompt="Faqat fotosintez jarayoni va xloroplastlar haqida savollar tuz",
            custom_instructions="Murakkab amaliy masalalar qo'shilsin"
        )
        assert req.question_count == 50
        assert req.prompt == "Faqat fotosintez jarayoni va xloroplastlar haqida savollar tuz"
        assert req.custom_instructions == "Murakkab amaliy masalalar qo'shilsin"

        # Verify max boundary: up to 100 is valid
        req100 = GenerateQuizRequest(question_count=100)
        assert req100.question_count == 100

        # Over 100 raises ValidationError
        with pytest.raises(ValidationError):
            GenerateQuizRequest(question_count=101)
