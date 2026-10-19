import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from apps.authentication.models import Organization
from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession

User = get_user_model()


@pytest.fixture
def org(db):
    return Organization.objects.create(
        name="17-Maktab",
        subscription_plan="pro",
        ai_monthly_token_budget=5_000_000
    )


@pytest.fixture
def teacher_user(db, org):
    user = User.objects.create_user(
        username="teacher_ali",
        email="ali@eduself.uz",
        password="SecurePassword123!",
        role="teacher",
        organization=org
    )
    return user


@pytest.fixture
def sample_quiz(db, teacher_user):
    return Quiz.objects.create(
        owner=teacher_user,
        title="Fizika: Nyuton Qonunlari",
        subject="physics",
        grade_level=8,
        status="published"
    )


@pytest.mark.django_db
class TestEduPlayUIViews:
    def test_index_unauthenticated_redirects_to_login(self):
        client = Client()
        response = client.get('/')
        assert response.status_code == 302
        assert response.url == '/login/'

    def test_index_authenticated_redirects_to_dashboard(self, teacher_user):
        client = Client()
        client.force_login(teacher_user)
        response = client.get('/')
        assert response.status_code == 302
        assert response.url == '/dashboard/'

    def test_login_page_renders_ok(self):
        client = Client()
        response = client.get('/login/')
        assert response.status_code == 200
        assert "Kirish" in response.content.decode('utf-8')
        assert "O‘qituvchi Tizimiga Kirish" in response.content.decode('utf-8')

    def test_login_submit_invalid_credentials(self):
        client = Client()
        response = client.post('/login/', {
            'username': 'wrong_user',
            'password': 'bad_password'
        })
        assert response.status_code == 200
        assert "Foydalanuvchi nomi yoki maxfiy parol" in response.content.decode('utf-8')

    def test_login_submit_valid_credentials(self, teacher_user):
        client = Client()
        response = client.post('/login/', {
            'username': 'teacher_ali',
            'password': 'SecurePassword123!'
        })
        assert response.status_code == 302
        assert response.url == '/dashboard/'

    def test_logout_redirects_to_login(self, teacher_user):
        client = Client()
        client.force_login(teacher_user)
        response = client.get('/logout/')
        assert response.status_code == 302
        assert response.url == '/login/'

    def test_profile_requires_login(self):
        client = Client()
        response = client.get('/profile/')
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_profile_authenticated(self, teacher_user):
        client = Client()
        client.force_login(teacher_user)
        response = client.get('/profile/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "teacher_ali" in content
        assert "17-Maktab" in content
        assert "Pro Teacher" in content

    def test_dashboard_requires_login(self):
        client = Client()
        response = client.get('/dashboard/')
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_dashboard_authenticated(self, teacher_user, sample_quiz):
        client = Client()
        client.force_login(teacher_user)
        response = client.get('/dashboard/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "teacher_ali" in content
        assert "Fizika: Nyuton Qonunlari" in content
        assert "Boshqaruv Paneli" in content

    def test_quiz_editor_new_requires_login(self):
        client = Client()
        response = client.get('/editor/new/')
        assert response.status_code == 302
        assert '/login/' in response.url

    def test_quiz_editor_new_authenticated(self, teacher_user):
        client = Client()
        client.force_login(teacher_user)
        response = client.get('/editor/new/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "Yangi Viktorina" in content
        assert "Muharrir" in content
        assert "Savol matni" in content

    def test_quiz_editor_existing_quiz(self, teacher_user, sample_quiz):
        client = Client()
        client.force_login(teacher_user)
        response = client.get(f'/editor/{sample_quiz.id}/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "Fizika: Nyuton Qonunlari" in content

    def test_launch_live_view(self, teacher_user, sample_quiz):
        client = Client()
        client.force_login(teacher_user)
        response = client.get(f'/live/launch/{sample_quiz.id}/')
        assert response.status_code == 302
        assert response.url.startswith('/live/')
        # Verify LiveSession created
        session = LiveSession.objects.filter(quiz=sample_quiz, host=teacher_user).first()
        assert session is not None
        assert session.status == 'lobby'
        assert len(session.room_code) == 6

    def test_host_screen_view(self, db):
        client = Client()
        response = client.get('/live/824190/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "824190" in content
        assert "JONLI EFIR" in content
        assert "Kutish zali" in content

    def test_student_game_view(self, db):
        client = Client()
        response = client.get('/play/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "O‘yinga Qo‘shilish" in content
        assert "Xona PIN kodi" in content

    def test_student_game_view_with_room_code(self, db):
        client = Client()
        response = client.get('/play/918273/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "918273" in content
