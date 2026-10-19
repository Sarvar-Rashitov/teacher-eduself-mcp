import json
import pytest
from django.contrib.auth import get_user_model

from apps.mcp_server.auth import MCPContext, mcp_context_scope
from apps.mcp_server.scopes import TEACHER_DEFAULT_SCOPES
from apps.mcp_server.tools.quiz_tools import (
    create_quiz_draft,
    get_quiz,
    update_quiz,
    validate_quiz,
    import_questions,
    list_question_sets,
)
from apps.mcp_server.exceptions import (
    MCPNotFoundError,
    MCPContentValidationError,
    MCPInvalidParamsError,
)
from apps.quizzes.models import Quiz, Question


User = get_user_model()


@pytest.fixture
def teacher_context(db):
    user = User.objects.create_user(
        username="mcp_teacher_quiz",
        email="teacher_quiz@eduself.uz",
        role="TEACHER",
    )
    return MCPContext(user=user, scopes=TEACHER_DEFAULT_SCOPES.copy())


@pytest.mark.django_db
def test_create_quiz_draft(teacher_context):
    with mcp_context_scope(teacher_context):
        res = create_quiz_draft(
            title="Biologiya 8-sinf",
            subject="Biologiya",
            grade_level=8,
            topic="Hujayra tuzilishi",
            question_count=10,
        )

        assert res["title"] == "Biologiya 8-sinf"
        assert res["status"].lower() == "draft"
        assert res["grade_level"] == 8

        quiz = Quiz.objects.get(id=res["quiz_id"])
        assert quiz.owner == teacher_context.user
        assert "Hujayra tuzilishi" in quiz.description


@pytest.mark.django_db
def test_create_quiz_draft_empty_title_raises_error(teacher_context):
    with mcp_context_scope(teacher_context):
        with pytest.raises(MCPInvalidParamsError):
            create_quiz_draft(title="", subject="Fizika", grade_level=7)


@pytest.mark.django_db
def test_get_quiz_details(teacher_context):
    with mcp_context_scope(teacher_context):
        draft = create_quiz_draft(title="Ona tili", subject="Ona tili", grade_level=6)
        quiz_id = draft["quiz_id"]

        quiz = Quiz.objects.get(id=quiz_id)
        Question.objects.create(
            quiz=quiz,
            type="single_choice",
            prompt="Ot so'z turkumi qanday so'roqlarga javob bo'ladi?",
            options=[
                {"id": "opt_1", "text": "Kim? Nima?", "is_correct": True},
                {"id": "opt_2", "text": "Qanday? Qanaqa?", "is_correct": False},
            ],
            correct_answer="opt_1",
            explanation="Ot kim yoki nima so'rog'iga javob beradi.",
            order_index=0,
        )

        data = get_quiz(quiz_id)
        assert data["title"] == "Ona tili"
        assert data["questions_count"] == 1
        assert data["questions"][0]["prompt"].startswith("Ot so'z")


@pytest.mark.django_db
def test_update_quiz_fields(teacher_context):
    with mcp_context_scope(teacher_context):
        draft = create_quiz_draft(title="Boshlang'ich nom", subject="Kimyo", grade_level=9)
        quiz_id = draft["quiz_id"]

        update_res = update_quiz(
            quiz_id=quiz_id,
            title="Yangilangan Kimyo",
            description="Tuzlarning formulalari",
            settings={"grade_level": 10},
        )

        assert update_res["status"] == "success"
        assert update_res["updated_version"] == 2

        quiz = Quiz.objects.get(id=quiz_id)
        assert quiz.title == "Yangilangan Kimyo"
        assert quiz.grade_level == 10


@pytest.mark.django_db
def test_validate_quiz(teacher_context):
    with mcp_context_scope(teacher_context):
        draft = create_quiz_draft(title="Informatika", subject="Informatika", grade_level=9)
        quiz_id = draft["quiz_id"]

        # Savolsiz holatda invalid bo'ladi
        val_res = validate_quiz(quiz_id)
        assert val_res["is_valid"] is False
        assert val_res["error_count"] > 0

        # Yaroqli savol qo'shamiz
        quiz = Quiz.objects.get(id=quiz_id)
        Question.objects.create(
            quiz=quiz,
            type="single_choice",
            prompt="1 bayt necha bitga teng?",
            options=[
                {"id": "opt_1", "text": "8 bit", "is_correct": True},
                {"id": "opt_2", "text": "16 bit", "is_correct": False},
            ],
            correct_answer="opt_1",
            order_index=0,
        )

        val_res2 = validate_quiz(quiz_id)
        assert val_res2["is_valid"] is True
        assert val_res2["error_count"] == 0


@pytest.mark.django_db
def test_import_questions_json(teacher_context):
    with mcp_context_scope(teacher_context):
        draft = create_quiz_draft(title="Astronomiya", subject="Fizika", grade_level=11)
        quiz_id = draft["quiz_id"]

        json_payload = json.dumps([
            {
                "type": "single_choice",
                "prompt": "Quyoshga eng yaqin sayyora qaysi?",
                "options": [
                    {"id": "opt_1", "text": "Merkuriy", "is_correct": True},
                    {"id": "opt_2", "text": "Venera", "is_correct": False},
                ],
                "correct_answer": "opt_1",
                "explanation": "Merkuriy quyosh tizimining 1-sayyorasi.",
                "points": 1000,
                "time_limit_seconds": 25,
            }
        ])

        import_res = import_questions(quiz_id=quiz_id, source_format="json", content=json_payload)
        assert import_res["status"] == "success"
        assert import_res["imported_count"] == 1

        quiz = Quiz.objects.get(id=quiz_id)
        assert quiz.questions.count() == 1


@pytest.mark.django_db
def test_import_questions_raw_text(teacher_context):
    with mcp_context_scope(teacher_context):
        draft = create_quiz_draft(title="Geografiya", subject="Geografiya", grade_level=7)
        quiz_id = draft["quiz_id"]

        raw_text = (
            "O'zbekiston poytaxti qaysi shahar?\n"
            "* Toshkent\n"
            "- Samarqand\n"
            "- Buxoro\n"
        )

        import_res = import_questions(quiz_id=quiz_id, source_format="raw_text", content=raw_text)
        assert import_res["status"] == "success"
        assert import_res["imported_count"] == 1

        quiz = Quiz.objects.get(id=quiz_id)
        assert quiz.questions.count() == 1
        q = quiz.questions.first()
        assert q.prompt.startswith("O'zbekiston poytaxti")
        assert len(q.options) == 3


@pytest.mark.django_db
def test_list_question_sets(teacher_context):
    with mcp_context_scope(teacher_context):
        create_quiz_draft(title="Matematika 1", subject="Matematika", grade_level=5)
        create_quiz_draft(title="Matematika 2", subject="Matematika", grade_level=6)
        create_quiz_draft(title="Tarix 1", subject="Tarix", grade_level=7)

        all_quizzes = list_question_sets()
        assert all_quizzes["total"] >= 3

        math_quizzes = list_question_sets(query="Matematika")
        assert math_quizzes["total"] == 2
