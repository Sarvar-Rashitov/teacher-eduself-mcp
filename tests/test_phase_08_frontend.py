"""
Automated Integration & Unit Tests for Phase 08:
Frontend Django MVT Templates, EduPlay 3D Design System,
Uzbek Mythological Dual-Coding, Web Audio API, and Vector SVG Iconography.
"""

import pytest
from pathlib import Path
from django.test import Client
from django.urls import reverse
from apps.authentication.models import User, Organization
from apps.quizzes.models import Quiz


@pytest.fixture
def test_teacher(db):
    org = Organization.objects.create(
        name="7-Maktab",
        subscription_plan="pro",
        ai_monthly_token_budget=1000000
    )
    user = User.objects.create_user(
        username="dilshod_teacher",
        email="dilshod@maktab.uz",
        password="ValidPassword123!",
        first_name="Dilshod",
        last_name="Karimov",
        role="teacher",
        organization=org
    )
    return user


@pytest.fixture
def test_quiz(db, test_teacher):
    quiz = Quiz.objects.create(
        owner=test_teacher,
        title="7-sinf Fizika Zichlik",
        description="Fizika kursi bo'yicha zichlik formulasi va masalalar",
        subject="Fizika",
        grade_level=7,
        status="published"
    )
    return quiz


@pytest.mark.django_db
class TestPhase08Frontend:
    """Test suite for EduSelf Phase 08 Frontend Templates and Assets."""

    def test_login_page_renders_ok(self):
        client = Client()
        response = client.get('/login/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "EduSelf" in content
        assert "Google orqali kirish" in content
        assert "Telegram orqali kirish" in content
        assert "google_logo.svg" in content
        assert "telegram_logo.svg" in content

    def test_profile_page_redirect_and_authenticated(self, test_teacher):
        client = Client()
        # Anonymous user must redirect to login
        anon_resp = client.get('/profile/')
        assert anon_resp.status_code == 302
        assert '/login/' in anon_resp.headers['Location']

        # Authenticated teacher gets 200
        client.force_login(test_teacher)
        auth_resp = client.get('/profile/')
        assert auth_resp.status_code == 200
        content = auth_resp.content.decode('utf-8')
        assert "Dilshod" in content
        assert "7-Maktab" in content
        assert "Pro" in content

    def test_teacher_dashboard_renders_ok(self, test_teacher, test_quiz):
        client = Client()
        client.force_login(test_teacher)
        
        for url in ['/', '/dashboard/']:
            response = client.get(url)
            assert response.status_code == 200
            content = response.content.decode('utf-8')
            assert "EduSelf" in content
            assert "Dilshod" in content
            assert "7-sinf Fizika Zichlik" in content
            assert "EduAI Yordamchisi" in content

    def test_quiz_editor_renders_ok(self, test_teacher, test_quiz):
        client = Client()
        client.force_login(test_teacher)

        # New quiz editor
        resp_new = client.get('/editor/new/')
        assert resp_new.status_code == 200
        new_content = resp_new.content.decode('utf-8')
        assert "Humo Qanoti" in new_content
        assert "Qanotli Tulpor" in new_content
        assert "Oltin Olma" in new_content
        assert "Boqiy Chinor" in new_content
        assert "humo_wing.svg" in new_content

        # Existing quiz editor
        resp_existing = client.get(f'/editor/{test_quiz.id}/')
        assert resp_existing.status_code == 200
        existing_content = resp_existing.content.decode('utf-8')
        assert "7-sinf Fizika Zichlik" in existing_content

    def test_host_screen_renders_ok(self):
        client = Client()
        response = client.get('/live/489201/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "489 201" in content or "489201" in content
        assert "EduSelf Live" in content
        assert "radialTimerCircle" in content
        assert "Humo Qanoti" in content
        assert "Shohsupa G‘oliblari" in content
        assert "royal_crown.svg" in content

    def test_student_game_renders_ok(self):
        client = Client()
        response = client.get('/play/489201/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "studentJoinScreen" in content
        assert "studentPlayScreen" in content
        assert "answer-btn-humo" in content
        assert "answer-btn-tulpor" in content
        assert "answer-btn-olma" in content
        assert "answer-btn-chinor" in content
        assert "PERFECT SCORER!" in content
        assert "NEXT LEVEL" in content

    def test_design_system_showcase_renders_ok(self):
        client = Client()
        response = client.get('/design-system/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "EduPlay 3D Design System" in content
        assert "Tanga Qilinglashi" in content
        assert "Humo Qanoti" in content
        assert "Qanotli Tulpor" in content
        assert "Oltin Olma" in content
        assert "Boqiy Chinor" in content
        assert "Madina K." in content
        assert "Sardorbek" in content
        assert "student_home.jpg" in content

    def test_static_files_accessible(self):
        base_dir = Path(__file__).resolve().parent.parent
        static_dir = base_dir / 'static'

        assert (static_dir / 'css' / 'eduplay_3d.css').exists()
        assert (static_dir / 'js' / 'audio.js').exists()
        assert (static_dir / 'js' / 'components.js').exists()
        assert (static_dir / 'js' / 'game_client.js').exists()

        # Check Mythological SVG icons
        icons_dir = static_dir / 'img' / 'icons'
        assert (icons_dir / 'humo_wing.svg').exists()
        assert (icons_dir / 'winged_tulpor.svg').exists()
        assert (icons_dir / 'golden_apple.svg').exists()
        assert (icons_dir / 'chinor_leaf.svg').exists()
        assert (icons_dir / 'gold_coin.svg').exists()
        assert (icons_dir / 'royal_crown.svg').exists()
        assert (icons_dir / 'fire_streak.svg').exists()
        assert (icons_dir / 'timer_clock.svg').exists()

    def test_vector_svg_iconography_in_templates(self):
        client = Client()
        pages = ['/login/', '/play/', '/design-system/']
        for page in pages:
            resp = client.get(page)
            assert resp.status_code == 200
            content = resp.content.decode('utf-8')
            assert ".svg" in content or "<svg" in content
