"""
Unit and integration tests for Quizzes CRUD, Question Registry validation, and Version Snapshotting.
"""

import uuid
import pytest
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.questions_registry.exceptions import QuestionValidationError, QuestionTypeNotFoundError
from apps.quizzes.models import Quiz, Question, QuizVersion
from apps.quizzes.services import QuizService


@pytest.fixture
def teacher(db):
    return User.objects.create_user(
        username="teacher_fizika",
        email="fizika@maktab.uz",
        role="teacher"
    )


@pytest.fixture
def auth_client(teacher):
    client = APIClient()
    client.force_authenticate(user=teacher)
    return client


# -----------------------------------------------------------------------------
# QuizService Unit Tests
# -----------------------------------------------------------------------------

@pytest.mark.django_db
def test_create_quiz(teacher):
    """Test creating a new draft quiz."""
    quiz = QuizService.create_quiz(
        owner=teacher,
        title="Optika asoslari",
        subject="Fizika",
        grade_level=8,
        locale="uz-Latn",
        description="8-sinf uchun optika mavzusidagi test"
    )
    assert isinstance(quiz.id, uuid.UUID)
    assert quiz.status == 'draft'
    assert quiz.current_version == 1
    assert quiz.question_count == 0


@pytest.mark.django_db
def test_add_valid_single_choice_question(teacher):
    """Test adding a validated single_choice question."""
    quiz = QuizService.create_quiz(owner=teacher, title="Fizika", subject="Fizika")
    q_data = {
        'type': 'single_choice',
        'prompt': 'Yorug‘lik tezligi vakuumda qancha?',
        'options': [
            {'id': 'opt_1', 'text': '300,000 km/s'},
            {'id': 'opt_2', 'text': '150,000 km/s'},
            {'id': 'opt_3', 'text': '30,000 km/s'},
        ],
        'correct_answer': 'opt_1',
        'points': 1000,
        'time_limit_seconds': 20,
    }
    question = QuizService.add_question(quiz, q_data)

    assert question.type == 'single_choice'
    assert question.order_index == 0
    assert question.points == 1000
    assert quiz.question_count == 1


@pytest.mark.django_db
def test_add_invalid_question_raises_validation_error(teacher):
    """Test adding a question with invalid payload raises QuestionValidationError."""
    quiz = QuizService.create_quiz(owner=teacher, title="Fizika", subject="Fizika")
    invalid_data = {
        'type': 'single_choice',
        'prompt': 'Savol',
        'options': [{'id': 'opt_1', 'text': 'Faqat bitta variant'}],  # Single choice needs >= 2
        'correct_answer': 'opt_1',
    }
    with pytest.raises(QuestionValidationError):
        QuizService.add_question(quiz, invalid_data)


@pytest.mark.django_db
def test_add_unregistered_question_type_raises_error(teacher):
    """Test adding an unregistered question type raises QuestionTypeNotFoundError."""
    quiz = QuizService.create_quiz(owner=teacher, title="Fizika", subject="Fizika")
    unknown_data = {
        'type': 'unknown_alien_format',
        'prompt': 'Savol',
        'options': [],
        'correct_answer': 'none',
    }
    with pytest.raises(QuestionTypeNotFoundError):
        QuizService.add_question(quiz, unknown_data)


@pytest.mark.django_db
def test_locked_question_cannot_be_overwritten(teacher):
    """Test that is_locked=True protects questions from modification unless unlocked."""
    quiz = QuizService.create_quiz(owner=teacher, title="Matematika", subject="Matematika")
    question = QuizService.add_question(quiz, {
        'type': 'single_choice',
        'prompt': '2 + 2 = ?',
        'options': [{'id': '1', 'text': '4'}, {'id': '2', 'text': '5'}],
        'correct_answer': '1',
        'is_locked': True
    })

    # Try updating without unlocking
    with pytest.raises(QuestionValidationError):
        QuizService.update_question(question, {'prompt': 'Yangi matn'})

    # Try deleting locked question
    with pytest.raises(QuestionValidationError):
        QuizService.delete_question(question)


@pytest.mark.django_db
def test_publish_quiz_version_creates_snapshot(teacher):
    """Test publishing creates frozen immutable snapshot in QuizVersion."""
    quiz = QuizService.create_quiz(owner=teacher, title="Tarix", subject="Tarix")
    QuizService.add_question(quiz, {
        'type': 'single_choice',
        'prompt': 'Amir Temur qachon tug‘ilgan?',
        'options': [{'id': 'a', 'text': '1336'}, {'id': 'b', 'text': '1405'}],
        'correct_answer': 'a',
    })

    version_record = QuizService.publish_quiz_version(quiz)

    assert version_record.version_number == 1
    assert quiz.current_version == 2
    assert quiz.status == 'published'
    assert 'questions' in version_record.snapshot_data
    assert len(version_record.snapshot_data['questions']) == 1


@pytest.mark.django_db
def test_zero_knowledge_student_preview_scrubs_secrets(teacher):
    """Zero-Knowledge test: verifies student representation omits correct answers and explanations."""
    quiz = QuizService.create_quiz(owner=teacher, title="Kimyo", subject="Kimyo")
    QuizService.add_question(quiz, {
        'type': 'single_choice',
        'prompt': 'Suvning kimyoviy formulasi?',
        'options': [
            {'id': 'opt_1', 'text': 'H2O', 'is_correct': True},
            {'id': 'opt_2', 'text': 'CO2', 'is_correct': False},
        ],
        'correct_answer': 'opt_1',
        'explanation': 'Suv ikki vodorod va bir kislorod atomidan tashkil topgan.',
    })

    student_data = QuizService.get_student_sanitized_quiz(quiz)
    q = student_data['questions'][0]

    # Secrets MUST be omitted
    assert 'correct_answer' not in q
    assert 'explanation' not in q
    assert 'accepted_alternatives' not in q

    # Options must NOT contain is_correct flag
    for opt in q['options']:
        assert 'is_correct' not in opt
        assert 'correct' not in opt


# -----------------------------------------------------------------------------
# REST API Endpoint Tests
# -----------------------------------------------------------------------------

@pytest.mark.django_db
def test_api_quiz_crud_and_preview(auth_client, teacher):
    """Test REST API endpoints for Quizzes."""
    # 1. Create Quiz
    create_res = auth_client.post('/api/v1/quizzes/', {
        'title': 'Biologiya Test',
        'subject': 'Biologiya',
        'grade_level': 9,
    })
    assert create_res.status_code == 201
    quiz_id = create_res.data['id']

    # 2. Add Question
    add_q_res = auth_client.post(f'/api/v1/quizzes/{quiz_id}/questions/', {
        'type': 'single_choice',
        'prompt': 'Inson tanasida nechta suyak bor?',
        'options': [{'id': '1', 'text': '206'}, {'id': '2', 'text': '300'}],
        'correct_answer': '1',
    }, format='json')
    assert add_q_res.status_code == 201

    # 3. Publish Quiz
    pub_res = auth_client.post(f'/api/v1/quizzes/{quiz_id}/publish/')
    assert pub_res.status_code == 201
    assert pub_res.data['version_number'] == 1

    # 4. Student Preview (Zero-Knowledge)
    prev_res = auth_client.get(f'/api/v1/quizzes/{quiz_id}/student-preview/')
    assert prev_res.status_code == 200
    assert 'correct_answer' not in prev_res.data['questions'][0]
