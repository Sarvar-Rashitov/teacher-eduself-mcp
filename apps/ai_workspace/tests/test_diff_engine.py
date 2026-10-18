import pytest
from django.contrib.auth import get_user_model
from apps.quizzes.models import Quiz, Question
from apps.ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIQuestionRevisionProposal,
)
from apps.ai_workspace.diff_engine import AIDiffEngine, LockedQuestionError

User = get_user_model()


@pytest.mark.django_db
def test_diff_engine_detects_prompt_and_options_changes():
    user = User.objects.create_user(username="teacher_diff", password="Password123!")
    quiz = Quiz.objects.create(title="Fizika Test", owner=user)
    question = Question.objects.create(
        quiz=quiz,
        order_index=0,
        type="single_choice",
        prompt="Yer Quyosh atrofida aylanadimi?",
        options=[{"id": "A", "text": "Ha"}, {"id": "B", "text": "Yo'q"}],
        correct_answer="A",
        explanation="Yer Quyosh tizimi sayyorasidir.",
        points=1000,
        time_limit_seconds=30,
        is_locked=False,
    )

    new_data = AIGeneratedQuestion(
        order=1,
        prompt="Yer Quyosh atrofida qanday trayektoriya bo'ylab aylanadi?",  # Changed
        options=[
            AIGeneratedOption(id="A", text="Ellips"),
            AIGeneratedOption(id="B", text="Doira"),
            AIGeneratedOption(id="C", text="To'g'ri chiziq"),
        ],  # Changed
        correct_answer="A",
        explanation="Keplerning birinchi qonuniga ko'ra ellips bo'ylab harakatlanadi.",
        points=1200,  # Changed
        time_limit_seconds=45,  # Changed
    )

    diff = AIDiffEngine.compute_question_diff(question, new_data, change_summary="Savol qiyinlashtirildi")

    assert diff.has_changes is True
    assert diff.is_locked is False

    changed_fields = {c.field for c in diff.changes if c.is_changed}
    assert "prompt" in changed_fields
    assert "options" in changed_fields
    assert "points" in changed_fields
    assert "time_limit_seconds" in changed_fields


@pytest.mark.django_db
def test_diff_engine_applies_proposal_to_unlocked_question():
    user = User.objects.create_user(username="teacher_apply", password="Password123!")
    quiz = Quiz.objects.create(title="Kimyo Test", owner=user)
    question = Question.objects.create(
        quiz=quiz,
        order_index=0,
        type="single_choice",
        prompt="Suv formulasi qaysi?",
        options=[{"id": "A", "text": "H2O"}, {"id": "B", "text": "CO2"}],
        correct_answer="A",
        points=1000,
        time_limit_seconds=30,
        is_locked=False,
    )

    proposal = AIQuestionRevisionProposal(
        question_order=1,
        change_summary="Izoh va ball yangilandi",
        modified_fields=["explanation", "points"],
        new_question_data=AIGeneratedQuestion(
            order=1,
            prompt="Suv formulasi qaysi?",
            options=[
                AIGeneratedOption(id="A", text="H2O"),
                AIGeneratedOption(id="B", text="CO2"),
                AIGeneratedOption(id="C", text="NaCl"),
            ],
            correct_answer="A",
            explanation="Suv 2 ta vodorod va 1 ta kislorod atomidan iborat.",
            points=1500,
            time_limit_seconds=30,
        ),
    )

    updated = AIDiffEngine.apply_proposal(question, proposal)
    assert updated.points == 1500
    assert updated.explanation == "Suv 2 ta vodorod va 1 ta kislorod atomidan iborat."
    assert len(updated.options) == 3


@pytest.mark.django_db
def test_diff_engine_blocks_modifying_locked_question():
    user = User.objects.create_user(username="teacher_locked", password="Password123!")
    quiz = Quiz.objects.create(title="Qulflangan Quiz", owner=user)
    question = Question.objects.create(
        quiz=quiz,
        order_index=0,
        type="single_choice",
        prompt="Daxlsiz savol",
        options=[{"id": "A", "text": "A"}, {"id": "B", "text": "B"}],
        correct_answer="A",
        is_locked=True,  # LOCKED!
    )

    proposal = AIQuestionRevisionProposal(
        question_order=1,
        change_summary="O'zgartirish urinishi",
        modified_fields=["prompt"],
        new_question_data=AIGeneratedQuestion(
            order=1,
            prompt="Buzib o'zgartirilgan savol",
            options=[AIGeneratedOption(id="A", text="A"), AIGeneratedOption(id="B", text="B")],
            correct_answer="A",
        ),
    )

    with pytest.raises(LockedQuestionError) as exc:
        AIDiffEngine.apply_proposal(question, proposal)
    assert "locked and cannot be modified" in str(exc.value)
