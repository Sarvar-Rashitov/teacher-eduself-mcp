import pytest
from unittest.mock import MagicMock
from django.contrib.auth import get_user_model
from apps.quizzes.models import Quiz, Question
from apps.ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIGeneratedQuiz,
    AIQuestionRevisionProposal,
    QuizRequirements,
)
from apps.ai_workspace.generator import AIQuizGenerator, LockedQuestionError

User = get_user_model()


def create_sample_quiz(title="Sample Quiz") -> AIGeneratedQuiz:
    return AIGeneratedQuiz(
        title=title,
        subject="Fizika",
        grade_level=8,
        questions=[
            AIGeneratedQuestion(
                order=1,
                prompt="Nyutonning birinchi qonuni nima haqida?",
                options=[
                    AIGeneratedOption(id="A", text="Inersiya haqida"),
                    AIGeneratedOption(id="B", text="Kuch haqida"),
                ],
                correct_answer="A",
            ),
            AIGeneratedQuestion(
                order=2,
                prompt="Tezlanish birligi qaysi?",
                options=[
                    AIGeneratedOption(id="A", text="$\\text{m/s}^2$"),
                    AIGeneratedOption(id="B", text="$\\text{m/s}$"),
                ],
                correct_answer="A",
            ),
        ]
    )


def test_generator_standard_flow():
    mock_router = MagicMock()
    mock_router.generate_structured.return_value = create_sample_quiz()

    generator = AIQuizGenerator(router=mock_router)
    req = QuizRequirements(subject="Fizika", grade_level=8, topic="Dinamika asoslari", question_count=2)

    result = generator.generate_quiz(req)
    assert result.title == "Sample Quiz"
    assert len(result.questions) == 2
    assert mock_router.generate_structured.call_count == 1


def test_generator_self_healing_retry_loop():
    mock_router = MagicMock()

    # Attempt 1: returns quiz with duplicate questions (triggering Tier 2 validation error)
    bad_quiz = AIGeneratedQuiz(
        title="Bad Quiz",
        subject="Kimyo",
        grade_level=7,
        questions=[
            AIGeneratedQuestion(
                order=1,
                prompt="Kislorod valentligi necha?",
                options=[AIGeneratedOption(id="A", text="II"), AIGeneratedOption(id="B", text="I")],
                correct_answer="A",
            ),
            AIGeneratedQuestion(
                order=2,
                prompt="Kislorod valentligi necha bo'ladi?",  # Duplicate!
                options=[AIGeneratedOption(id="A", text="II"), AIGeneratedOption(id="B", text="I")],
                correct_answer="A",
            ),
        ]
    )

    # Attempt 2: returns repaired valid quiz
    good_quiz = create_sample_quiz(title="Repaired Quiz")

    mock_router.generate_structured.side_effect = [bad_quiz, good_quiz]

    generator = AIQuizGenerator(router=mock_router)
    req = QuizRequirements(subject="Kimyo", grade_level=7, topic="Valentlik", question_count=2)

    result = generator.generate_quiz(req, max_self_healing_retries=2)

    # Verify self-healing made 2 attempts and returned good quiz
    assert mock_router.generate_structured.call_count == 2
    assert result.title == "Repaired Quiz"


@pytest.mark.django_db
def test_generator_revise_question_and_locking():
    user = User.objects.create_user(username="teacher_gen", password="Password123!")
    quiz = Quiz.objects.create(title="Biologiya", owner=user)
    q1 = Question.objects.create(
        quiz=quiz,
        order_index=0,
        prompt="Hujayra nima?",
        options=[{"id": "A", "text": "Tiriklik birligi"}, {"id": "B", "text": "Molekula"}],
        correct_answer="A",
        is_locked=False,
    )
    q2 = Question.objects.create(
        quiz=quiz,
        order_index=1,
        prompt="DNK qayerda joylashgan?",
        options=[{"id": "A", "text": "Yadroda"}, {"id": "B", "text": "Sitoplazmada"}],
        correct_answer="A",
        is_locked=True,  # LOCKED!
    )

    mock_router = MagicMock()
    mock_router.generate_structured.return_value = AIQuestionRevisionProposal(
        question_order=1,
        change_summary="Izoh qo'shildi",
        modified_fields=["explanation"],
        new_question_data=AIGeneratedQuestion(
            order=1,
            prompt="Hujayra nima?",
            options=[AIGeneratedOption(id="A", text="Tiriklik birligi"), AIGeneratedOption(id="B", text="Molekula")],
            correct_answer="A",
            explanation="Hujayra barcha tirik organizmlarning tuzilish birligidir.",
        ),
    )

    generator = AIQuizGenerator(router=mock_router)

    # Revise unlocked question (q1) -> Success
    proposal = generator.revise_question(quiz, question_order=1, instruction="Izoh qo'sh")
    assert proposal.question_order == 1
    assert "explanation" in proposal.modified_fields

    # Revise locked question (q2) -> Must raise LockedQuestionError
    with pytest.raises(LockedQuestionError):
        generator.revise_question(quiz, question_order=2, instruction="Variantlarni o'zgartir")


@pytest.mark.django_db
def test_regenerate_quiz_preserving_locked_questions():
    user = User.objects.create_user(username="teacher_preserve", password="Password123!")
    quiz = Quiz.objects.create(title="Tarix", owner=user)
    # Question 1 is locked
    Question.objects.create(
        quiz=quiz,
        order_index=0,
        prompt="Amir Temur qachon tug'ilgan?",
        options=[{"id": "A", "text": "1336-yil"}, {"id": "B", "text": "1405-yil"}],
        correct_answer="A",
        is_locked=True,
    )
    # Question 2 is unlocked
    Question.objects.create(
        quiz=quiz,
        order_index=1,
        prompt="Alisher Navoiy qachon tug'ilgan?",
        options=[{"id": "A", "text": "1441-yil"}, {"id": "B", "text": "1501-yil"}],
        correct_answer="A",
        is_locked=False,
    )

    # Mock generator returning new questions
    generated_quiz = AIGeneratedQuiz(
        title="Yangi Tarix",
        subject="Tarix",
        grade_level=7,
        questions=[
            AIGeneratedQuestion(
                order=1,
                prompt="Mirzo Ulug'bek rasadxonasi qayerda?",
                options=[AIGeneratedOption(id="A", text="Samarqandda"), AIGeneratedOption(id="B", text="Buxoroda")],
                correct_answer="A",
            ),
            AIGeneratedQuestion(
                order=2,
                prompt="Bobur qachon tug'ilgan?",
                options=[AIGeneratedOption(id="A", text="1483-yil"), AIGeneratedOption(id="B", text="1530-yil")],
                correct_answer="A",
            ),
        ]
    )

    mock_router = MagicMock()
    mock_router.generate_structured.return_value = generated_quiz

    generator = AIQuizGenerator(router=mock_router)
    req = QuizRequirements(subject="Tarix", grade_level=7, topic="Temuriylar davri", question_count=2)

    merged_quiz = generator.regenerate_quiz_preserving_locked(quiz, req)

    # Question 1 MUST remain the locked "Amir Temur qachon tug'ilgan?"
    assert merged_quiz.questions[0].order == 1
    assert merged_quiz.questions[0].prompt == "Amir Temur qachon tug'ilgan?"

    # Question 2 is replaced by newly generated question
    assert merged_quiz.questions[1].order == 2
    assert merged_quiz.questions[1].prompt == "Mirzo Ulug'bek rasadxonasi qayerda?"
