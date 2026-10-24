"""
Integration Tests for all MCP Core Tools (DOC-82) and Zero-Bypass Multi-Tenant Protection.
"""

import pytest
import json
from django.contrib.auth import get_user_model
from django.test import Client
from apps.authentication.models import Organization
from apps.quizzes.models import Quiz
from apps.quizzes.services import QuizCRUDService
from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission
from apps.live_sessions.fsm import SessionState
from apps.mcp_server.auth import generate_mcp_token, MCPAuthContextManager
from apps.mcp_server.scopes import Scopes
from apps.mcp_server.exceptions import (
    MCPForbiddenError,
    MCPNotFoundError,
    MCPInvalidSessionStateError,
)
from apps.mcp_server.tools import quiz_tools, session_tools, analytics_tools
from apps.mcp_server.server import dispatch_tool

User = get_user_model()


@pytest.mark.django_db
class TestMCPQuizTools:
    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.org = Organization.objects.create(name="Toshkent Gimnaziya")
        self.teacher_1 = User.objects.create_user(
            username="teacher_alisher",
            email="alisher@eduself.uz",
            organization=self.org,
            role="teacher",
        )
        self.teacher_2 = User.objects.create_user(
            username="teacher_madina",
            email="madina@eduself.uz",
            role="teacher",
        )
        self.client = Client()

    def test_create_and_get_quiz_draft(self):
        """create_quiz_draft va get_quiz to'g'ri ishlashi kerak."""
        with MCPAuthContextManager(user=self.teacher_1, scopes=list(Scopes.ALL)):
            created = quiz_tools.create_quiz_draft(
                title="Biologiya 7-sinf",
                subject="Biologiya",
                grade_level=7,
                topic="Hujayra tuzilishi",
                questions=[
                    {
                        "type": "single_choice",
                        "prompt": "O'simlik hujayrasida fotosintez qayerda sodir bo'ladi?",
                        "options": [
                            {"id": "opt_1", "text": "Xloroplast"},
                            {"id": "opt_2", "text": "Mitoxondriya"},
                            {"id": "opt_3", "text": "Ribosoma"},
                        ],
                        "correct_answer": "opt_1",
                        "points": 1000,
                        "time_limit_seconds": 30,
                    }
                ],
            )
            assert created["status"] == "draft"
            assert created["created_questions"] == 1
            quiz_id = created["quiz_id"]

            # get_quiz chaqiruvi
            fetched = quiz_tools.get_quiz(quiz_id=quiz_id)
            assert fetched["title"] == "Biologiya 7-sinf"
            assert fetched["questions_count"] == 1
            assert fetched["questions"][0]["prompt"] == "O'simlik hujayrasida fotosintez qayerda sodir bo'ladi?"

    def test_zero_bypass_cross_tenant_isolation(self):
        """Boshqa o'qituvchining viktorinasiga MCP orqali kirish 403 Forbidden berishi SHART."""
        # Teacher 1 viktorina yaratadi
        quiz = QuizCRUDService.create_quiz(
            owner=self.teacher_1,
            title="Maxfiy Fizika Testi",
            subject="Fizika",
        )

        # Teacher 2 ushbu viktorinani o'qishga urinadi
        with MCPAuthContextManager(user=self.teacher_2, scopes=list(Scopes.ALL)):
            with pytest.raises(MCPForbiddenError) as exc_info:
                quiz_tools.get_quiz(quiz_id=str(quiz.id))
            assert "taqiqlangan" in str(exc_info.value).lower()

    def test_update_and_validate_quiz(self):
        """update_quiz va validate_quiz ishlashi tekshiruvi."""
        with MCPAuthContextManager(user=self.teacher_1, scopes=list(Scopes.ALL)):
            created = quiz_tools.create_quiz_draft(
                title="Kimyo boshlang'ich",
                subject="Kimyo",
            )
            q_id = created["quiz_id"]

            # Yangilash
            res = quiz_tools.update_quiz(quiz_id=q_id, changes={"title": "Kimyo 8-sinf Chuqurlashtirilgan"})
            assert res["status"] == "success"
            assert res["updated_version"] == 2

            # Validatsiya
            val = quiz_tools.validate_quiz(quiz_id=q_id)
            assert "is_valid" in val
            assert "errors" in val

    def test_import_questions_json_and_csv(self):
        """import_questions yordamida CSV va JSON savollarni yuklash."""
        with MCPAuthContextManager(user=self.teacher_1, scopes=list(Scopes.ALL)):
            quiz = quiz_tools.create_quiz_draft(title="Geografiya", subject="Geografiya")
            q_id = quiz["quiz_id"]

            # JSON import
            json_data = json.dumps([
                {
                    "type": "single_choice",
                    "prompt": "O'zbekiston poytaxti qaysi shahar?",
                    "options": [
                        {"id": "o1", "text": "Toshkent"},
                        {"id": "o2", "text": "Samarqand"},
                    ],
                    "correct_answer": "o1",
                }
            ])
            res_json = quiz_tools.import_questions(quiz_id=q_id, source_format="json", content=json_data)
            assert res_json["imported_count"] == 1

            # CSV import
            csv_data = "prompt,options,correct_answer,points,time_limit\nDunyoning eng baland cho'qqisi qaysi?,Everest|Monblan,opt_1,1000,30"
            res_csv = quiz_tools.import_questions(quiz_id=q_id, source_format="csv", content=csv_data)
            assert res_csv["imported_count"] == 1

            # Savollar soni jami 2 ta bo'lishi kerak
            full_quiz = quiz_tools.get_quiz(quiz_id=q_id)
            assert full_quiz["questions_count"] == 2


@pytest.mark.django_db
class TestMCPSessionAndAnalyticsTools:
    @pytest.fixture(autouse=True)
    def setup_session_data(self):
        self.teacher = User.objects.create_user(
            username="teacher_shaxzod",
            email="shaxzod@eduself.uz",
            role="teacher",
        )
        self.quiz = QuizCRUDService.create_quiz(
            owner=self.teacher,
            title="Matematika Jonli Musobaqa",
            subject="Matematika",
        )
        self.q1 = QuizCRUDService.add_question(self.quiz, {
            "type": "single_choice",
            "prompt": "7 * 8 nechiga teng?",
            "options": [{"id": "a", "text": "56"}, {"id": "b", "text": "54"}],
            "correct_answer": "a",
            "points": 1000,
        })
        self.q2 = QuizCRUDService.add_question(self.quiz, {
            "type": "single_choice",
            "prompt": "12 ning kvadrati qancha?",
            "options": [{"id": "a", "text": "144"}, {"id": "b", "text": "124"}],
            "correct_answer": "a",
            "points": 1000,
        })

    def test_full_session_lifecycle_via_mcp(self):
        """Sessiyani yaratish, boshlash, oldinga surish, javoblarni ko'rish va yakunlash."""
        with MCPAuthContextManager(user=self.teacher, scopes=list(Scopes.ALL)):
            # 1. create_live_session
            session_res = session_tools.create_live_session(quiz_id=str(self.quiz.id), game_mode="classic")
            session_id = session_res["session_id"]
            assert len(session_res["pin"]) == 6
            assert session_res["status"] == SessionState.LOBBY

            # 2. get_session_status
            status = session_tools.get_session_status(session_id)
            assert status["status"] == SessionState.LOBBY
            assert status["total_questions"] == 2

            # O'quvchi qo'shamiz
            session_obj = LiveSession.objects.get(id=session_id)
            from apps.live_sessions.services import LiveSessionService
            p1, _ = LiveSessionService.join_session(session_res["pin"], "Jasur")
            p1.score = 1000
            p1.save(update_fields=["score"])
            p2, _ = LiveSessionService.join_session(session_res["pin"], "Sardor")
            p2.score = 800
            p2.save(update_fields=["score"])

            # 3. start_session
            start_res = session_tools.start_session(session_id)
            assert start_res["status"] == SessionState.ACTIVE
            assert start_res["current_question_index"] == 0

            # 4. advance_question
            adv_res = session_tools.advance_question(session_id)
            assert adv_res["current_question_index"] == 1
            assert adv_res["has_more_questions"] is True

            # 5. reveal_answers
            rev_res = session_tools.reveal_answers(session_id)
            assert rev_res["question_prompt"] == "12 ning kvadrati qancha?"
            assert rev_res["correct_answer"] == "a"

            # 6. end_session
            end_res = session_tools.end_session(session_id)
            assert end_res["status"] == SessionState.COMPLETED
            assert len(end_res["top_podium"]) == 2
            assert end_res["top_podium"][0]["nickname"] == "Jasur"

    def test_invalid_fsm_transition_raises_error(self):
        """Allaqachon yakunlangan sessiyani qayta boshlash taqiqlanadi."""
        with MCPAuthContextManager(user=self.teacher, scopes=list(Scopes.ALL)):
            sess = session_tools.create_live_session(quiz_id=str(self.quiz.id))
            session_id = sess["session_id"]
            session_tools.start_session(session_id)
            session_tools.end_session(session_id)

            # Tugallangan sessiyani yana start qilishga urinish
            with pytest.raises(MCPInvalidSessionStateError):
                session_tools.start_session(session_id)

    def test_team_game_and_report_and_followup_activity(self):
        """Jamoalarga taqsimlash, tahliliy hisobot va mustahkamlovchi dars yaratish."""
        with MCPAuthContextManager(user=self.teacher, scopes=list(Scopes.ALL)):
            sess = session_tools.create_live_session(quiz_id=str(self.quiz.id))
            session_id = sess["session_id"]
            session_obj = LiveSession.objects.get(id=session_id)

            # 4 nafar o'quvchi
            from apps.live_sessions.services import LiveSessionService
            for name in ["Aziz", "Barno", "Charos", "Davron"]:
                p, _ = LiveSessionService.join_session(sess["pin"], name)
                p.score = 500
                p.save(update_fields=["score"])

            # 1. create_team_game
            team_res = analytics_tools.create_team_game(session_id=session_id, team_count=2)
            assert team_res["team_count"] == 2
            assert len(team_res["teams"]) == 2
            assert sum(t["member_count"] for t in team_res["teams"]) == 4

            # 2. get_session_report
            report = analytics_tools.get_session_report(session_id=session_id)
            assert report["quiz_title"] == "Matematika Jonli Musobaqa"
            assert report["total_participants"] == 4
            assert len(report["questions_analysis"]) == 2

            # 3. generate_followup_activity
            followup = analytics_tools.generate_followup_activity(session_id=session_id)
            assert "Mustahkamlovchi dars" in followup["title"]
            assert followup["focus_questions_count"] > 0

    def test_jsonrpc_http_tools_call_dispatch(self):
        """HTTP orqali JSON-RPC 2.0 tools/call chaqiruvini tekshirish."""
        token = generate_mcp_token(self.teacher, scopes=list(Scopes.ALL))
        client = Client()

        payload = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "create_quiz_draft",
                "arguments": {
                    "title": "JSON-RPC Orqali Yaratilgan Test",
                    "subject": "Informatika",
                },
            },
        }

        response = client.post(
            "/mcp/messages",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 42
        assert "result" in data
        assert data["result"]["structured"]["title"] == "JSON-RPC Orqali Yaratilgan Test"
