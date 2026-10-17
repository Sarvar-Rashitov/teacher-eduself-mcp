import pytest
from rest_framework.test import APIClient
from rest_framework import status
from apps.authentication.models import User
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession


@pytest.fixture
def api_teacher(db):
    return User.objects.create_user(
        username="api_teacher_session",
        password="password123",
        role="teacher"
    )


@pytest.fixture
def api_quiz(db, api_teacher):
    quiz = Quiz.objects.create(
        title="Kimyo Asoslari",
        subject="Kimyo",
        grade_level=8,
        owner=api_teacher
    )
    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="Suvning kimyoviy formulasi qaysi?",
        options=[
            {"id": "opt_1", "text": "H2O"},
            {"id": "opt_2", "text": "CO2"},
            {"id": "opt_3", "text": "NaCl"},
        ],
        correct_answer={"correct_option_id": "opt_1"},
        points=1000,
        time_limit_seconds=20,
        order_index=0
    )
    return quiz


@pytest.mark.django_db
def test_create_session_api(api_teacher, api_quiz):
    client = APIClient()
    client.force_authenticate(user=api_teacher)

    url = "/api/v1/sessions/create/"
    payload = {
        "quiz_id": str(api_quiz.id),
        "game_mode": "classic",
        "settings_payload": {"speed_bonus": True}
    }
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    data = response.data
    assert data['status'] == 'ok'
    assert 'host_ticket' in data
    assert 'session' in data
    assert len(data['session']['room_code']) == 6


@pytest.mark.django_db
def test_join_session_api(api_teacher, api_quiz):
    # Teacher creates session
    client = APIClient()
    client.force_authenticate(user=api_teacher)
    create_res = client.post("/api/v1/sessions/create/", {"quiz_id": str(api_quiz.id)}, format="json")
    room_code = create_res.data['session']['room_code']

    # Student joins without login (Anonymous student)
    anon_client = APIClient()
    join_payload = {
        "room_code": room_code,
        "nickname": "Temur",
        "team_name": "Bars"
    }
    join_res = anon_client.post("/api/v1/sessions/join/", join_payload, format="json")
    assert join_res.status_code == status.HTTP_200_OK
    assert join_res.data['nickname'] == "Temur"
    assert 'ticket' in join_res.data
    assert 'anonymous_token' in join_res.data


@pytest.mark.django_db
def test_session_state_api(api_teacher, api_quiz):
    client = APIClient()
    client.force_authenticate(user=api_teacher)
    create_res = client.post("/api/v1/sessions/create/", {"quiz_id": str(api_quiz.id)}, format="json")
    room_code = create_res.data['session']['room_code']

    # Anonymous get state
    anon_client = APIClient()
    state_res = anon_client.get(f"/api/v1/sessions/{room_code}/state/")
    assert state_res.status_code == status.HTTP_200_OK
    assert state_res.data['room_code'] == room_code
    assert state_res.data['total_questions'] == 1
    # Zero-Knowledge: student state preview must not leak correct_answer
    assert 'correct_answer' not in state_res.data['current_question']
