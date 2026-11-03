import pytest
import time
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.mcp_server.auth import (
    authenticate_bearer_token,
    generate_mcp_token,
    mcp_context_scope,
    get_current_mcp_context,
    MCPContext,
)
from apps.mcp_server.scopes import (
    require_scope,
    SCOPE_QUIZ_READ,
    SCOPE_QUIZ_WRITE,
    SCOPE_SESSION_CONTROL,
)
from apps.mcp_server.exceptions import (
    MCPUnauthorizedError,
    MCPForbiddenError,
)
from apps.quizzes.models import Quiz
from apps.mcp_server.tools.quiz_tools import get_quiz


User = get_user_model()


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username="teacher_mcp_1",
        email="teacher1@eduself.uz",
        role="TEACHER",
    )


@pytest.fixture
def other_teacher(db):
    return User.objects.create_user(
        username="teacher_mcp_2",
        email="teacher2@eduself.uz",
        role="TEACHER",
    )


@pytest.mark.django_db
def test_authenticate_valid_token(teacher_user):
    token = generate_mcp_token(teacher_user, scopes=[SCOPE_QUIZ_READ, SCOPE_QUIZ_WRITE])
    context = authenticate_bearer_token(f"Bearer {token}")

    assert context.user.id == teacher_user.id
    assert SCOPE_QUIZ_READ in context.scopes
    assert SCOPE_QUIZ_WRITE in context.scopes
    assert context.client_name == "claude-desktop"


@pytest.mark.django_db
def test_authenticate_expired_token(teacher_user):
    token = generate_mcp_token(teacher_user, expires_in=-10)
    with pytest.raises(MCPUnauthorizedError) as exc_info:
        authenticate_bearer_token(f"Bearer {token}")

    assert "muddati o'tgan" in str(exc_info.value).lower()
    assert exc_info.value.code == -32001


def test_authenticate_missing_or_empty_token():
    with pytest.raises(MCPUnauthorizedError):
        authenticate_bearer_token("")

    with pytest.raises(MCPUnauthorizedError):
        authenticate_bearer_token("Bearer ")


def test_authenticate_tampered_token(teacher_user):
    token = generate_mcp_token(teacher_user)
    tampered = token[:-4] + "abcd"
    with pytest.raises(MCPUnauthorizedError):
        authenticate_bearer_token(f"Bearer {tampered}")


@pytest.mark.django_db
def test_require_scope_decorator_success(teacher_user):
    @require_scope(SCOPE_QUIZ_READ)
    def protected_action():
        return "allowed"

    ctx = MCPContext(user=teacher_user, scopes={SCOPE_QUIZ_READ})
    with mcp_context_scope(ctx):
        res = protected_action()
        assert res == "allowed"


@pytest.mark.django_db
def test_require_scope_decorator_forbidden(teacher_user):
    @require_scope(SCOPE_SESSION_CONTROL)
    def control_action():
        return "session_controlled"

    # Faqat quiz:read bor, session:control yo'q
    ctx = MCPContext(user=teacher_user, scopes={SCOPE_QUIZ_READ})
    with mcp_context_scope(ctx):
        with pytest.raises(MCPForbiddenError) as exc_info:
            control_action()
        assert exc_info.value.code == -32003
        assert "session:control" in str(exc_info.value)


@pytest.mark.django_db
def test_tenant_isolation_prevents_access_to_other_teacher_quiz(teacher_user, other_teacher):
    # O'qituvchi 2 ga tegishli viktorina
    foreign_quiz = Quiz.objects.create(
        title="Boshqa o'qituvchi testi",
        owner=other_teacher,
        status="DRAFT",
    )

    # O'qituvchi 1 nomidan kiramiz
    ctx = MCPContext(user=teacher_user, scopes={SCOPE_QUIZ_READ})
    with mcp_context_scope(ctx):
        with pytest.raises(MCPForbiddenError) as exc_info:
            get_quiz(str(foreign_quiz.id))
        assert exc_info.value.code == -32003
        assert "taqiqlangan" in str(exc_info.value).lower()
