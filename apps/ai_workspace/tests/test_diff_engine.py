import pytest
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

from quizzes.models import Quiz, Question
from ai_workspace.diff_engine import AIDiffEngine
from ai_workspace.schemas import (
    AIQuestionRevisionProposal,
    AIGeneratedQuestion,
    AIGeneratedOption,
    QuestionTypeEnum,
    DifficultyEnum,
)

User = get_user_model()


@pytest.mark.django_db
class TestAIDiffEngine:
    @pytest.fixture
    def setup_data(self):
        user = User.objects.create_user(
            username="teacher_diff",
            email="teacher_diff@test.com",
            password="testpassword123",
            role="teacher",
        )
        quiz = Quiz.objects.create(
            owner=user,
            title="Tarixiy sanalar",
            subject="Tarix",
            grade_level=7,
        )
        question = Question.objects.create(
            quiz=quiz,
            type="single_choice",
            prompt="Amir Temur nechanchi yilda tavallud topgan?",
            options=[
                {"id": "A", "text": "1336"},
                {"id": "B", "text": "1346"},
                {"id": "C", "text": "1356"},
                {"id": "D", "text": "1366"},
            ],
            correct_answer={"correct_option_id": "A"},
            explanation="Amir Temur 1336-yil 9-aprelda tug'ilgan.",
            points=1000,
            time_limit_seconds=30,
            difficulty="medium",
            order_index=1,
            is_locked=False,
            version=1,
        )
        return {"user": user, "quiz": quiz, "question": question}

    def test_propose_revision_detects_changes(self, setup_data):
        question = setup_data["question"]
        engine = AIDiffEngine()

        proposal = AIQuestionRevisionProposal(
            question_order=1,
            change_summary="Vaqt va ball yangilandi, tushuntirish kengaytirildi",
            modified_fields=["explanation", "time_limit_seconds", "points"],
            original_question_data={"prompt": question.prompt},
            new_question_data=AIGeneratedQuestion(
                order=1,
                prompt=question.prompt,
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="1336"),
                    AIGeneratedOption(id="B", text="1346"),
                    AIGeneratedOption(id="C", text="1356"),
                    AIGeneratedOption(id="D", text="1366"),
                ],
                correct_answer={"correct_option_id": "A"},
                explanation="Kengaytirilgan izoh: Kesh yaqinidagi Xo'ja Ilg'or qishlog'ida.",
                time_limit_seconds=20,
                points=1200,
                difficulty=DifficultyEnum.MEDIUM,
            ),
        )

        diff_res = engine.propose_revision(question, proposal)

        assert diff_res["question_id"] == str(question.id)
        assert diff_res["change_summary"] == "Vaqt va ball yangilandi, tushuntirish kengaytirildi"
        assert "time_limit_seconds" in diff_res["diffs"]
        assert diff_res["diffs"]["time_limit_seconds"]["before"] == 30
        assert diff_res["diffs"]["time_limit_seconds"]["after"] == 20
        assert diff_res["diffs"]["points"]["after"] == 1200
        assert "prompt" not in diff_res["diffs"]  # unchanged

    def test_question_lock_guardrail_blocks_propose_revision(self, setup_data):
        question = setup_data["question"]
        question.is_locked = True
        question.save()

        engine = AIDiffEngine()
        proposal = AIQuestionRevisionProposal(
            question_order=1,
            change_summary="Qulflangan savolga taklif",
            new_question_data=AIGeneratedQuestion(
                order=1,
                prompt="Yangi savol matni",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="1"),
                    AIGeneratedOption(id="B", text="2"),
                ],
                correct_answer="A",
            ),
        )

        with pytest.raises(PermissionDenied) as exc_info:
            engine.propose_revision(question, proposal)

        assert "qulflangan" in str(exc_info.value).lower()

    def test_apply_proposal_updates_model_and_increments_version(self, setup_data):
        question = setup_data["question"]
        engine = AIDiffEngine()

        proposal = AIQuestionRevisionProposal(
            question_order=1,
            change_summary="Savol matni va vaqt o'zgartirildi",
            new_question_data=AIGeneratedQuestion(
                order=1,
                prompt="Sohibqiron Amir Temur qaysi yilda tavallud topgan?",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="1336-yil"),
                    AIGeneratedOption(id="B", text="1346-yil"),
                    AIGeneratedOption(id="C", text="1356-yil"),
                    AIGeneratedOption(id="D", text="1366-yil"),
                ],
                correct_answer={"correct_option_id": "A"},
                explanation="1336-yil 9-aprel.",
                time_limit_seconds=25,
                points=1000,
                difficulty=DifficultyEnum.MEDIUM,
            ),
        )

        updated = engine.apply_proposal(question, proposal)

        assert updated.prompt == "Sohibqiron Amir Temur qaysi yilda tavallud topgan?"
        assert updated.time_limit_seconds == 25
        assert updated.version == 2
        assert updated.options[0]["text"] == "1336-yil"

        # Verify from database
        question.refresh_from_db()
        assert question.prompt == "Sohibqiron Amir Temur qaysi yilda tavallud topgan?"
        assert question.version == 2

    def test_question_lock_guardrail_blocks_apply_proposal(self, setup_data):
        question = setup_data["question"]
        question.is_locked = True
        question.save()

        engine = AIDiffEngine()
        proposal = AIQuestionRevisionProposal(
            question_order=1,
            change_summary="Buzg'unchi AI tahrir",
            new_question_data=AIGeneratedQuestion(
                order=1,
                prompt="Qulflangan savolni o'zgartirish",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="Ha"),
                    AIGeneratedOption(id="B", text="Yo'q"),
                ],
                correct_answer="A",
            ),
        )

        with pytest.raises(PermissionDenied) as exc_info:
            engine.apply_proposal(question, proposal)

        assert "qulflangan" in str(exc_info.value).lower()
        # Verify database model was NOT altered
        question.refresh_from_db()
        assert "Amir Temur nechanchi yilda" in question.prompt
        assert question.version == 1
