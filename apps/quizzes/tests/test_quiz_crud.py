import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.quizzes.models import Quiz, Question, QuizVersion
from apps.quizzes.services import QuizService
# Question types yuklanishi uchun
import apps.questions_registry.types  # noqa: F401


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username='teacher_sarah',
        email='sarah@example.com',
        password='Password123!',
        role='teacher'
    )


@pytest.fixture
def sample_quiz(db, teacher_user):
    return QuizService.create_quiz(
        owner=teacher_user,
        title='Fizika: Nyuton Qonunlari',
        subject='Fizika',
        grade_level=7,
        locale='uz-Latn'
    )


@pytest.mark.django_db
class TestQuizService:
    def test_create_quiz(self, teacher_user):
        """QuizService orqali qoralama quiz yaratish."""
        quiz = QuizService.create_quiz(
            owner=teacher_user,
            title='Kimyo asoslari',
            subject='Kimyo',
            grade_level=8
        )
        assert quiz.status == 'draft'
        assert quiz.current_version == 1
        assert quiz.owner == teacher_user

    def test_add_valid_question(self, sample_quiz):
        """To'g'ri formatdagi savol qo'shilganda saqlanishi va versiya oshishi."""
        q = QuizService.add_question(
            quiz=sample_quiz,
            type_id='single_choice',
            prompt='Og\'irlik kuchi formulasi qaysi?',
            options=[
                {'id': 'A', 'text': 'F = ma'},
                {'id': 'B', 'text': 'F = mg'},
                {'id': 'C', 'text': 'E = mc^2'}
            ],
            correct_answer={'selected_option_id': 'B'},
            points=1000,
            time_limit_seconds=20
        )
        assert q.quiz == sample_quiz
        assert q.points == 1000
        assert q.order_index == 0
        sample_quiz.refresh_from_db()
        assert sample_quiz.current_version == 2
        assert sample_quiz.question_count == 1

    def test_add_invalid_question_raises_error(self, sample_quiz):
        """Mavjud bo'lmagan to'g'ri javob ID si berilganda ValidationError chiqishi."""
        with pytest.raises(ValidationError):
            QuizService.add_question(
                quiz=sample_quiz,
                type_id='single_choice',
                prompt='Noto\'g\'ri savol',
                options=[
                    {'id': 'A', 'text': '1'},
                    {'id': 'B', 'text': '2'}
                ],
                correct_answer={'selected_option_id': 'Z_INVALID'}  # Mavjud emas!
            )

    def test_create_version_snapshot(self, sample_quiz):
        """QuizVersion snapshot yaratilishi va muzlatilishi."""
        QuizService.add_question(
            quiz=sample_quiz,
            type_id='true_false',
            prompt='Yer Quyosh atrofida aylanadi.',
            options=[{'id': 'true', 'text': "To'g'ri"}, {'id': 'false', 'text': "Noto'g'ri"}],
            correct_answer={'value': True}
        )

        version = QuizService.create_version_snapshot(sample_quiz)
        assert isinstance(version, QuizVersion)
        assert version.version_number == sample_quiz.current_version
        assert 'questions' in version.snapshot_data
        assert len(version.snapshot_data['questions']) == 1

    def test_zero_knowledge_student_sanitization(self, sample_quiz):
        """Student savollarida correct_answer mutlaqo bo'lmasligi (Zero-Knowledge)."""
        QuizService.add_question(
            quiz=sample_quiz,
            type_id='single_choice',
            prompt='Quyosh tizimining eng katta sayyorasi?',
            options=[
                {'id': 'A', 'text': 'Mars'},
                {'id': 'B', 'text': 'Yupiter'}
            ],
            correct_answer={'selected_option_id': 'B'},
            explanation='Yupiter eng ulkan gaz giganti hisoblanadi.'
        )

        sanitized = QuizService.get_sanitized_questions_for_student(sample_quiz)
        assert len(sanitized) == 1
        q_data = sanitized[0]

        # Maxfiy kalitlar chiqarib tashlangan bo'lishi shart!
        assert 'correct_answer' not in q_data
        assert 'accepted_alternatives' not in q_data
        assert 'explanation' not in q_data
        assert q_data['prompt'] == 'Quyosh tizimining eng katta sayyorasi?'
        assert len(q_data['options']) == 2

    def test_locked_question_ai_protection(self, sample_quiz):
        """is_locked=True bo'lgan savol AI tomonidan o'zgartirilishi taqiqlanishi."""
        q = QuizService.add_question(
            quiz=sample_quiz,
            type_id='true_false',
            prompt='Asl savol',
            options=[],
            correct_answer={'value': True},
            is_locked=True
        )

        # AI amal qilganda xatolik berishi kerak
        with pytest.raises(ValidationError):
            QuizService.update_question(q, is_ai_action=True, prompt='AI o\'zgartirgan savol')


@pytest.mark.django_db
class TestQuizAPIViews:
    def test_quiz_crud_endpoints(self, teacher_user):
        client = APIClient()
        client.force_authenticate(user=teacher_user)

        # 1. Create Quiz
        create_url = reverse('quizzes:quiz-list')
        resp = client.post(create_url, {
            'title': 'Biologiya 9-sinf',
            'subject': 'Biologiya',
            'grade_level': 9,
            'locale': 'uz-Latn'
        }, format='json')
        assert resp.status_code == 201
        quiz_id = resp.data['id']

        # 2. List Quizzes
        list_resp = client.get(create_url)
        assert list_resp.status_code == 200
        assert len(list_resp.data['results'] if 'results' in list_resp.data else list_resp.data) >= 1

        # 3. Add Question via QuestionViewSet
        q_create_url = reverse('quizzes:question-list')
        q_resp = client.post(q_create_url, {
            'quiz': quiz_id,
            'type': 'single_choice',
            'prompt': 'Hujayra yadrosi nima?',
            'options': [{'id': 'A', 'text': 'Organoid'}, {'id': 'B', 'text': 'Modda'}],
            'correct_answer': {'selected_option_id': 'A'},
            'points': 1000,
            'time_limit_seconds': 30
        }, format='json')
        assert q_resp.status_code == 201
        q_id = q_resp.data['id']

        # 4. Toggle lock
        lock_url = reverse('quizzes:question-toggle-lock', kwargs={'pk': q_id})
        lock_resp = client.post(lock_url)
        assert lock_resp.status_code == 200
        assert lock_resp.data['is_locked'] is True

        # 5. Student Preview endpoint
        preview_url = reverse('quizzes:quiz-student-preview', kwargs={'pk': quiz_id})
        prev_resp = client.get(preview_url)
        assert prev_resp.status_code == 200
        assert len(prev_resp.data['questions']) == 1
        assert 'correct_answer' not in prev_resp.data['questions'][0]

        # 6. Snapshot endpoint
        snapshot_url = reverse('quizzes:quiz-create-snapshot', kwargs={'pk': quiz_id})
        snap_resp = client.post(snapshot_url)
        assert snap_resp.status_code == 201
        assert 'snapshot_data' in snap_resp.data
