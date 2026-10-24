import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from quizzes.models import Quiz, Question, QuizVersion
from quizzes.services import QuizCRUD, VersionManager, QuestionValidator

User = get_user_model()


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username="teacher_ali",
        email="ali@eduself.uz",
        password="SecurePassword2026!",
        first_name="Ali",
        role="teacher",
    )


@pytest.fixture
def sample_quiz(db, teacher_user):
    return QuizCRUD.create_quiz(
        owner=teacher_user,
        data={
            "title": "O'zbekiston Tarixi - 7-sinf",
            "subject": "Tarix",
            "grade_level": 7,
            "locale": "uz-Latn",
            "description": "Amir Temur davri bo'yicha viktorina",
            "status": "draft",
        }
    )


@pytest.fixture
def single_choice_payload():
    return {
        "type": "single_choice",
        "prompt": "Amir Temur qachon tavallud topgan?",
        "options": [
            {"id": "opt_1", "text": "1336-yil 9-aprel"},
            {"id": "opt_2", "text": "1340-yil 1-may"},
            {"id": "opt_3", "text": "1441-yil 9-fevral"},
        ],
        "correct_answer": {"correct_option_id": "opt_1"},
        "explanation": "Amir Temur 1336-yil 9-aprelda Xo'ja Ilg'or qishlog'ida tug'ilgan.",
        "points": 1000,
        "time_limit_seconds": 30,
    }


@pytest.mark.django_db
class TestQuizCRUD:
    def test_create_quiz(self, teacher_user):
        quiz = QuizCRUD.create_quiz(
            owner=teacher_user,
            data={"title": "Fizika 8-sinf", "subject": "Fizika", "grade_level": 8}
        )
        assert quiz.id is not None
        assert quiz.owner == teacher_user
        assert quiz.status == "draft"
        assert quiz.current_version == 1
        assert quiz.grade_level == 8

    def test_update_quiz(self, sample_quiz):
        updated = QuizCRUD.update_quiz(sample_quiz, {"title": "Yangi Sarlavha", "grade_level": 9})
        assert updated.title == "Yangi Sarlavha"
        assert updated.grade_level == 9

    def test_add_valid_question(self, sample_quiz, single_choice_payload):
        question = QuizCRUD.add_question(sample_quiz, single_choice_payload)
        assert question.id is not None
        assert question.quiz == sample_quiz
        assert question.order_index == 0
        assert question.type == "single_choice"
        assert question.points == 1000
        assert sample_quiz.questions.count() == 1

    def test_add_invalid_question_raises_validation_error(self, sample_quiz):
        # Invalid: option count < 2
        bad_payload = {
            "type": "single_choice",
            "prompt": "Savol?",
            "options": [{"id": "1", "text": "Bitta variant"}],
            "correct_answer": {"correct_option_id": "1"},
        }
        with pytest.raises(ValidationError):
            QuizCRUD.add_question(sample_quiz, bad_payload)

        # Invalid: correct_option_id not in options
        bad_answer_payload = {
            "type": "single_choice",
            "prompt": "Savol 2?",
            "options": [
                {"id": "1", "text": "A"},
                {"id": "2", "text": "B"},
            ],
            "correct_answer": {"correct_option_id": "non_existent_id"},
        }
        with pytest.raises(ValidationError):
            QuizCRUD.add_question(sample_quiz, bad_answer_payload)

    def test_locked_question_protection(self, sample_quiz, single_choice_payload):
        single_choice_payload["is_locked"] = True
        question = QuizCRUD.add_question(sample_quiz, single_choice_payload)
        assert question.is_locked is True

        # Attempt to modify locked question without override should fail
        with pytest.raises(ValidationError, match="is_locked=True"):
            QuizCRUD.update_question(question, {"prompt": "O'zgartirilgan matn"})

        # Modification with override_locked=True succeeds
        updated = QuizCRUD.update_question(
            question,
            {"prompt": "O'zgartirilgan matn"},
            override_locked=True
        )
        assert updated.prompt == "O'zgartirilgan matn"

        # Attempt to delete locked question without override should fail
        with pytest.raises(ValidationError, match="is_locked=True"):
            QuizCRUD.delete_question(question)

        # Deletion with override_locked=True succeeds
        QuizCRUD.delete_question(question, override_locked=True)
        assert sample_quiz.questions.count() == 0

    def test_reorder_questions(self, sample_quiz, single_choice_payload):
        q1 = QuizCRUD.add_question(sample_quiz, single_choice_payload)

        payload2 = dict(single_choice_payload)
        payload2["prompt"] = "2-savol"
        q2 = QuizCRUD.add_question(sample_quiz, payload2)

        assert q1.order_index == 0
        assert q2.order_index == 1

        # Reverse the order
        updated = QuizCRUD.reorder_questions(sample_quiz, [str(q2.id), str(q1.id)])
        q1.refresh_from_db()
        q2.refresh_from_db()

        assert q2.order_index == 0
        assert q1.order_index == 1

    def test_publish_quiz_creates_snapshot(self, sample_quiz, single_choice_payload):
        # Empty quiz publish raises ValidationError
        with pytest.raises(ValidationError, match="kamida bitta savol"):
            QuizCRUD.publish_quiz(sample_quiz)

        # Add question and publish
        QuizCRUD.add_question(sample_quiz, single_choice_payload)
        published = QuizCRUD.publish_quiz(sample_quiz)

        assert published.status == "published"
        assert published.versions.count() == 1
        snapshot = published.versions.first()
        assert snapshot.version_number == 1
        assert snapshot.snapshot_data["total_questions"] == 1


@pytest.mark.django_db
class TestZeroKnowledgeSanitization:
    def test_student_view_completely_strips_secret_answers(self, sample_quiz, single_choice_payload):
        # Add single_choice
        QuizCRUD.add_question(sample_quiz, single_choice_payload)

        # Add multiple_choice
        QuizCRUD.add_question(sample_quiz, {
            "type": "multiple_choice",
            "prompt": "Temuriylar davri me'moriy obidalari?",
            "options": [
                {"id": "A", "text": "Go'ri Amir", "is_correct": True},
                {"id": "B", "text": "Bibixonim", "is_correct": True},
                {"id": "C", "text": "Registon", "is_correct": True},
                {"id": "D", "text": "Eyfel minorasi", "is_correct": False},
            ],
            "correct_answer": {"correct_option_ids": ["A", "B", "C"]},
            "explanation": "Go'ri Amir va Bibixonim Samarqandda joylashgan.",
        })

        # Add short_text
        QuizCRUD.add_question(sample_quiz, {
            "type": "open_short",
            "prompt": "Quyosh sistemasidagi eng katta sayyora?",
            "correct_answer": {"accepted_answers": ["Yupiter", "Jupiter"]},
            "explanation": "Yupiter gaz giganti hisoblanadi.",
        })

        sanitized_bundle = QuizCRUD.get_sanitized_quiz(sample_quiz)
        assert sanitized_bundle["total_questions"] == 3

        for q in sanitized_bundle["questions"]:
            assert "correct_answer" not in q
            assert "correct_answer_key" not in q
            assert "explanation" not in q
            assert "accepted_alternatives" not in q
            assert "accepted_answers" not in q

            if isinstance(q.get("options"), list):
                for opt in q["options"]:
                    if isinstance(opt, dict):
                        assert "is_correct" not in opt

    def test_student_view_api_endpoint(self, sample_quiz, single_choice_payload):
        QuizCRUD.add_question(sample_quiz, single_choice_payload)
        client = APIClient()

        url = f"/api/v1/quizzes/{sample_quiz.id}/student_view/"
        response = client.get(url)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(sample_quiz.id)
        assert len(data["questions"]) == 1
        q = data["questions"][0]

        # Critical security check: No answer leak
        assert "correct_answer" not in q
        assert "explanation" not in q
        assert "is_correct" not in q["options"][0]


@pytest.mark.django_db
class TestVersionManager:
    def test_version_snapshots_history(self, sample_quiz, single_choice_payload):
        QuizCRUD.add_question(sample_quiz, single_choice_payload)

        v1 = VersionManager.create_snapshot(sample_quiz, change_log="Boshlang'ich versiya")
        assert v1.version_number == 1
        assert sample_quiz.current_version == 1

        # Add another question and snapshot v2
        payload2 = dict(single_choice_payload)
        payload2["prompt"] = "2-savol"
        QuizCRUD.add_question(sample_quiz, payload2)

        v2 = VersionManager.create_snapshot(sample_quiz, change_log="2-savol qo'shildi")
        assert v2.version_number == 2
        assert sample_quiz.current_version == 2
        assert sample_quiz.versions.count() == 2

        # Verify snapshot isolation (v1 had 1 question, v2 has 2)
        assert v1.snapshot_data["total_questions"] == 1
        assert v2.snapshot_data["total_questions"] == 2


@pytest.mark.django_db
class TestQuizAPIEndpoints:
    def test_quiz_rest_api_flow(self, teacher_user, single_choice_payload):
        client = APIClient()
        client.force_authenticate(user=teacher_user)

        # 1. Create Quiz via API
        create_res = client.post("/api/v1/quizzes/", {
            "title": "Kimyo 9-sinf",
            "subject": "Kimyo",
            "grade_level": 9,
            "status": "draft",
        }, format="json")
        assert create_res.status_code == 201
        quiz_id = create_res.json()["id"]

        # 2. Add Question via API
        question_payload = dict(single_choice_payload)
        question_payload["quiz"] = quiz_id
        q_res = client.post("/api/v1/quizzes/questions/", question_payload, format="json")
        assert q_res.status_code == 201

        # 3. Retrieve Quiz (Teacher View)
        get_res = client.get(f"/api/v1/quizzes/{quiz_id}/")
        assert get_res.status_code == 200
        assert get_res.json()["total_questions"] == 1
        # Teacher view has correct_answer
        assert "correct_answer" in get_res.json()["questions"][0]

        # 4. Publish Quiz via API
        pub_res = client.post(f"/api/v1/quizzes/{quiz_id}/publish/")
        assert pub_res.status_code == 200
        assert pub_res.json()["status"] == "published"

        # 5. Get Versions via API
        ver_res = client.get(f"/api/v1/quizzes/{quiz_id}/versions/")
        assert ver_res.status_code == 200
        assert len(ver_res.json()) >= 1
