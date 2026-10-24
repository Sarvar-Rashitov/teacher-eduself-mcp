"""
Verification tests for Phase 00 core infrastructure and contracts.
"""

from core.contracts.quiz_contract import QuizDTO, QuestionDTO
from core.contracts.scoring_contract import AnswerSubmissionDTO, ScoringEngineProtocol
from core.contracts.ai_contract import GeneratedQuizPayload, GeneratedQuestionSchema


def test_quiz_contract_dto():
    """Verify Quiz and Question DTO instantiation."""
    q = QuestionDTO(
        id="q-1",
        type="single_choice",
        prompt="O'zbekiston poytaxti qaysi shahar?",
        options=[{"text": "Toshkent", "id": "opt-1"}, {"text": "Samarqand", "id": "opt-2"}],
        correct_answer="opt-1",
        points=1000,
        time_limit_seconds=30,
    )
    quiz = QuizDTO(
        id="quiz-1",
        title="Geografiya Viktorinasi",
        questions=[q],
    )
    assert quiz.id == "quiz-1"
    assert len(quiz.questions) == 1
    assert quiz.questions[0].prompt == "O'zbekiston poytaxti qaysi shahar?"


def test_scoring_contract_dto():
    """Verify AnswerSubmissionDTO and ScoringEngineProtocol structure."""
    submission = AnswerSubmissionDTO(
        participant_id="user-123",
        question_id="q-1",
        user_answer="opt-1",
        time_taken_ms=3500,
        streak_count=2,
    )
    assert submission.participant_id == "user-123"
    assert submission.time_taken_ms == 3500
    assert submission.streak_count == 2


def test_ai_contract_pydantic_schema():
    """Verify AI contract schema validation with valid payload."""
    payload_data = {
        "title": "Tarix Testi",
        "subject": "O'zbekiston Tarixi",
        "grade_level": 8,
        "locale": "uz-Latn",
        "questions": [
            {
                "type": "single_choice",
                "prompt": "Amir Temur nechanchi yilda tavallud topgan?",
                "options": [
                    {"id": "a", "text": "1336-yil"},
                    {"id": "b", "text": "1441-yil"},
                ],
                "correct_answer": "a",
                "explanation": "Amir Temur 1336-yil 9-aprelda Xo'ja Ilg'or qishlog'ida tug'ilgan.",
                "difficulty": "medium",
                "points": 1000,
                "time_limit_seconds": 30,
            }
        ],
    }
    quiz_payload = GeneratedQuizPayload(**payload_data)
    assert quiz_payload.title == "Tarix Testi"
    assert len(quiz_payload.questions) == 1
    assert quiz_payload.questions[0].correct_answer == "a"
