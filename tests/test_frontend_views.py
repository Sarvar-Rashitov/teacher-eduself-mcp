"""
Integration and Rendering Tests for Frontend MVT Templates & Views (Phase 08).
Validates HTML rendering, dual-coded answer buttons, audio scripts, and static linking.
"""

import pytest
from django.test import Client
from django.contrib.auth import get_user_model
from apps.quizzes.services import QuizCRUDService
from apps.live_sessions.services import LiveSessionService

User = get_user_model()


@pytest.mark.django_db
class TestFrontendMVTViews:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username="teacher_shirin",
            email="shirin@eduself.uz",
            password="securepassword123",
            role="teacher",
        )
        self.quiz = QuizCRUDService.create_quiz(
            owner=self.teacher,
            title="Tarix 7-sinf Temuriylar",
            subject="Tarix",
            grade_level=7,
        )
        self.session = LiveSessionService.create_session(
            host=self.teacher,
            quiz=self.quiz,
            game_mode="classic",
        )

    def test_anonymous_redirects_to_login(self):
        """Kirilmagan foydalanuvchi /dashboard/ ga kirganda /auth/login/ ga yo'naltiriladi."""
        response = self.client.get("/dashboard/")
        assert response.status_code == 302
        assert "/auth/login/" in response.url

    def test_login_page_renders_cleanly(self):
        """GET /auth/login/ 200 OK qaytaradi va Google/Telegram tugmalari mavjud."""
        response = self.client.get("/auth/login/")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "EduSelf" in content
        assert "Google orqali kirish" in content
        assert "Telegram orqali kirish" in content
        assert "eduplay_3d.css" in content
        assert "audio.js" in content

    def test_dashboard_renders_for_logged_in_teacher(self):
        """Kirgan o'qituvchi /dashboard/ da o'z testlarini ko'rishi kerak."""
        self.client.force_login(self.teacher)
        response = self.client.get("/dashboard/")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Darslar va O‘yinlar Boshqaruvi" in content
        assert "Tarix 7-sinf Temuriylar" in content
        assert "PLAY EARN WIN" in content

    def test_profile_page_renders(self):
        """GET /auth/profile/ profil ma'lumotlarini to'g'ri chiqaradi."""
        self.client.force_login(self.teacher)
        response = self.client.get("/auth/profile/")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "teacher_shirin" in content
        assert "shirin@eduself.uz" in content

    def test_quiz_editor_renders(self):
        """/editor/new/ va /editor/<id>/ muharrir sahifasini ochadi."""
        self.client.force_login(self.teacher)

        # Yangi viktorina
        resp_new = self.client.get("/editor/new/")
        assert resp_new.status_code == 200
        assert "Savol Matni" in resp_new.content.decode("utf-8")

        # Mavjud viktorina
        resp_existing = self.client.get(f"/editor/{self.quiz.id}/")
        assert resp_existing.status_code == 200
        assert "Tarix 7-sinf Temuriylar" in resp_existing.content.decode("utf-8")

    def test_host_screen_renders_with_pin(self):
        """/live/<room_code>/ proyektor ekranida 6 xonali PIN kod chiqadi."""
        response = self.client.get(f"/live/{self.session.room_code}/")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert self.session.room_code in content
        assert "Proyektori" in content
        assert "game_client.js" in content

    def test_student_game_renders_dual_coded_buttons(self):
        """/play/<room_code>/ mobil o'yinchi ekranida 4 xil geometrik shakl mavjud (▲, ◆, ●, ■)."""
        response = self.client.get(f"/play/{self.session.room_code}/")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        # Dual-coding accessibility check:
        assert "▲" in content  # Red Triangle
        assert "◆" in content  # Blue Diamond
        assert "●" in content  # Yellow Circle
        assert "■" in content  # Green Square
        assert "game_client.js" in content
        assert "audio.js" in content

    def test_student_game_view_no_fallback_without_code(self):
        """/play/ xona kodi ko'rsatilmaganda zaxira testlar yuklanmaydi, bo'sh ro'yxat qaytadi."""
        response = self.client.get("/play/")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "studentQuestionsData" in content
        assert "[]" in content

    def test_student_join_api_success_and_invalid_code(self):
        """POST /api/sessions/join/ haqiqiy xona savollarini qaytaradi, noto'g'ri kodda 400 beradi."""
        from apps.quizzes.models import Question
        Question.objects.create(
            quiz=self.quiz,
            order_index=1,
            prompt="Amir Temur nechanchi yilda tug'ilgan?",
            options=[{"id": "opt_1", "text": "1336"}, {"id": "opt_2", "text": "1405"}],
            correct_answer="opt_1",
            time_limit_seconds=20,
            points=1000,
        )

        # 1. Muvaffaqiyatli ulanish
        res_ok = self.client.post("/api/sessions/join/", data={
            "room_code": self.session.room_code,
            "nickname": "Azizbek",
        }, content_type="application/json")
        assert res_ok.status_code == 200
        data_ok = res_ok.json()
        assert data_ok["status"] == "ok"
        assert data_ok["nickname"] == "Azizbek"
        assert len(data_ok["questions"]) == 1
        assert data_ok["questions"][0]["prompt"] == "Amir Temur nechanchi yilda tug'ilgan?"

        # 2. Mavjud bo'lmagan PIN kod
        res_bad = self.client.post("/api/sessions/join/", data={
            "room_code": "999999",
            "nickname": "Azizbek",
        }, content_type="application/json")
        assert res_bad.status_code == 400
        assert "error" in res_bad.json()
