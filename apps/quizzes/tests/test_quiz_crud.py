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


@pytest.mark.django_db
def test_api_quiz_save_full_with_multiple_question_types(auth_client, teacher):
    """Test bulk saving a quiz with multiple 14 question types in a single atomic transaction."""
    payload = {
        'title': 'Universal 14 Question Types Assessment',
        'subject': 'Fizika',
        'grade_level': 8,
        'status': 'published',
        'description': 'Universal test with various question formats',
        'questions': [
            {
                'type': 'single_choice',
                'prompt': 'Yorug‘lik tezligi?',
                'options': [{'id': 'opt_1', 'text': '300,000 km/s'}, {'id': 'opt_2', 'text': '150,000 km/s'}],
                'correct_answer': 'opt_1',
                'points': 1000,
                'time_limit_seconds': 30
            },
            {
                'type': 'multiple_choice',
                'prompt': 'Vektor kattaliklarni tanlang:',
                'options': [{'id': 'opt_1', 'text': 'Tezlik'}, {'id': 'opt_2', 'text': 'Kuch'}, {'id': 'opt_3', 'text': 'Massa'}],
                'correct_answer': ['opt_1', 'opt_2'],
                'points': 1000,
                'time_limit_seconds': 30
            },
            {
                'type': 'true_false',
                'prompt': 'Suv 100 darajada qaynaydi.',
                'options': [{'id': 'true', 'text': 'Rost'}, {'id': 'false', 'text': 'Yolg‘on'}],
                'correct_answer': 'true',
                'points': 1000,
                'time_limit_seconds': 20
            },
            {
                'type': 'open_short',
                'prompt': 'O‘zbekiston poytaxti qaysi shahar?',
                'options': [],
                'correct_answer': 'Toshkent',
                'accepted_alternatives': ['Tashkent'],
                'points': 1000,
                'time_limit_seconds': 30
            },
            {
                'type': 'numeric',
                'prompt': 'Vakuumdagi yorug‘lik tezligi (km/s):',
                'options': {'tolerance': 100},
                'correct_answer': {'value': 300000, 'tolerance': 100},
                'points': 1000,
                'time_limit_seconds': 30
            },
            {
                'type': 'slider',
                'prompt': 'O‘rtacha inson tanasi harorati:',
                'options': {'min': 34, 'max': 42},
                'correct_answer': {'target': 36.6, 'tolerance': 0.5},
                'points': 1000,
                'time_limit_seconds': 30
            },
            {
                'type': 'math_equation',
                'prompt': 'Nyutonning 2-qonuni formulasi:',
                'options': [],
                'correct_answer': 'F = m * a',
                'points': 1000,
                'time_limit_seconds': 30
            },
            {
                'type': 'code_output',
                'prompt': 'Natijani toping: print(10 + 20)',
                'options': {'language': 'python', 'code': 'print(10 + 20)'},
                'correct_answer': '30',
                'points': 1000,
                'time_limit_seconds': 30
            },
            {
                'type': 'ordering',
                'prompt': 'Bosqichlarni joylashtiring:',
                'options': [{'id': 's1', 'text': 'Gipoteza'}, {'id': 's2', 'text': 'Tajriba'}],
                'correct_answer': ['s1', 's2'],
                'points': 1000,
                'time_limit_seconds': 30
            },
            {
                'type': 'match_pairs',
                'prompt': 'Juftliklarni moslashtiring:',
                'options': [{'id': 'p1', 'left': 'Massa', 'right': 'kg'}, {'id': 'p2', 'left': 'Vaqt', 'right': 's'}],
                'correct_answer': {'p1': 'p1', 'p2': 'p2'},
                'points': 1000,
                'time_limit_seconds': 30
            }
        ]
    }

    # 1. Create quiz with bulk save
    res = auth_client.post('/api/v1/quizzes/save-full/', payload, format='json')
    assert res.status_code == 201
    quiz_id = res.data['quiz_id']
    assert quiz_id is not None

    quiz = Quiz.objects.get(id=quiz_id)
    assert quiz.title == 'Universal 14 Question Types Assessment'
    assert quiz.status == 'published'
    assert quiz.questions.count() == 10
    # Published quiz must create QuizVersion snapshot
    assert quiz.versions.count() == 1

    # 2. Update existing quiz: change title and modify questions
    payload['id'] = quiz_id
    payload['title'] = 'Yangilangan Viktorina'
    # Keep only first 2 questions and add 1 new
    payload['questions'] = payload['questions'][:2]
    payload['questions'].append({
        'type': 'open_short',
        'prompt': 'Yangi savol?',
        'options': [],
        'correct_answer': 'Javob',
        'points': 1000,
        'time_limit_seconds': 30
    })

    update_res = auth_client.post('/api/v1/quizzes/save-full/', payload, format='json')
    assert update_res.status_code == 200

    quiz.refresh_from_db()
    assert quiz.title == 'Yangilangan Viktorina'
    assert quiz.questions.count() == 3


@pytest.mark.django_db
def test_api_quiz_save_full_validation_failure(auth_client):
    """Test that invalid question payload aborts transaction with 400 error."""
    payload = {
        'title': 'Xato Savol Test',
        'subject': 'Fizika',
        'questions': [
            {
                'type': 'single_choice',
                'prompt': 'Xato variantlar',
                'options': [{'id': 'opt_1', 'text': 'Faqat bitta variant'}], # Invalid: < 2 options
                'correct_answer': 'opt_1',
            }
        ]
    }
    res = auth_client.post('/api/v1/quizzes/save-full/', payload, format='json')
    assert res.status_code == 400
    assert 'xatosi' in res.data['error']


@pytest.mark.django_db
def test_teacher_dashboard_dynamic_metrics(teacher):
    """Test that teacher dashboard renders real metrics calculated from database."""
    from django.test import Client
    from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission

    # Create 2 quizzes
    q1 = Quiz.objects.create(owner=teacher, title="Viktorina 1", subject="Fizika", grade_level=7, status="published")
    q2 = Quiz.objects.create(owner=teacher, title="Viktorina 2", subject="Matematika", grade_level=8, status="draft")

    # Create 1 LiveSession
    session = LiveSession.objects.create(
        quiz=q1,
        host=teacher,
        room_code="123456",
        status="completed"
    )

    # Create 2 Participants
    p1 = Participant.objects.create(session=session, nickname="Ali", score=1000)
    p2 = Participant.objects.create(session=session, nickname="Vali", score=500)

    # Create Questions & Submissions: 2 correct, 1 incorrect => accuracy 67%
    quest = Question.objects.create(
        quiz=q1,
        type="single_choice",
        prompt="Savol",
        options=[{"id": "1", "text": "A"}],
        correct_answer="1"
    )
    AnswerSubmission.objects.create(session=session, participant=p1, question=quest, submission_id=str(uuid.uuid4()), is_correct=True)
    AnswerSubmission.objects.create(session=session, participant=p2, question=quest, submission_id=str(uuid.uuid4()), is_correct=True)
    AnswerSubmission.objects.create(session=session, participant=p1, question=quest, submission_id=str(uuid.uuid4()), is_correct=False)

    client = Client()
    client.force_login(teacher)
    response = client.get('/dashboard/')
    assert response.status_code == 200
    ctx = response.context
    assert ctx['quizzes_count'] == 2
    assert ctx['completed_sessions_count'] == 1
    assert ctx['active_students_count'] == 2
    assert ctx['average_accuracy'] == 67

    content = response.content.decode('utf-8')
    assert "Viktorina 1" in content
    assert "Viktorina 2" in content
    assert "67%" in content
