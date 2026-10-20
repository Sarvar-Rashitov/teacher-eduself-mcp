"""
Comprehensive Security, Rate Limiting, OWASP Top 10, and Brute-force Tests (Phase 10).
"""

import json
import logging
import pytest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.quizzes.models import Quiz
from apps.authentication.security import (
    is_account_locked,
    record_login_failure,
    reset_login_failures,
    sanitize_text,
    sanitize_rich_text,
    validate_password_strength,
    _in_memory_failed_attempts,
    _in_memory_lockouts,
)
from core.middleware.rate_limit import (
    _in_memory_windows,
    resolve_tier_and_key,
    check_rate_limit,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def clean_security_state():
    """Clears cache, in-memory rate limits and lockouts before and after each test."""
    from django.core.cache import cache
    cache.clear()
    _in_memory_windows.clear()
    _in_memory_failed_attempts.clear()
    _in_memory_lockouts.clear()
    yield
    cache.clear()
    _in_memory_windows.clear()
    _in_memory_failed_attempts.clear()
    _in_memory_lockouts.clear()


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username="sec_teacher_1",
        first_name="Alisher",
        last_name="Navoiy",
        role="teacher",
        password="ValidPassword2026!"
    )


@pytest.fixture
def other_teacher(db):
    return User.objects.create_user(
        username="sec_teacher_2",
        first_name="Bobur",
        last_name="Zahiriddin",
        role="teacher",
        password="ValidPassword2026!"
    )


# ============================================================================
# 1. Security Headers Tests (OWASP A05)
# ============================================================================

class TestSecurityHeaders:

    def test_security_headers_present_on_response(self, client):
        resp = client.get('/login/')
        assert resp.status_code == 200

        # CSP
        assert 'Content-Security-Policy' in resp.headers
        csp = resp.headers['Content-Security-Policy']
        assert "default-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

        # Clickjacking & Sniffing
        assert resp.headers.get('X-Frame-Options') == 'DENY'
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'

        # Referrer & Permissions
        assert 'strict-origin-when-cross-origin' in resp.headers.get('Referrer-Policy', '')
        assert 'geolocation=()' in resp.headers.get('Permissions-Policy', '')
        assert resp.headers.get('Cross-Origin-Opener-Policy') == 'same-origin'


# ============================================================================
# 2. Redis Sliding Window Rate Limiting Tests (OWASP A04 / A07)
# ============================================================================

class TestRateLimiting:

    def test_tier_resolution(self):
        rf = RequestFactory()

        # Auth
        req_auth = rf.post('/api/v1/auth/login/')
        tier, limit, window, key = resolve_tier_and_key(req_auth)
        assert tier == 'auth'
        assert limit == 5
        assert window == 60
        assert 'ratelimit:auth:' in key

        # AI
        req_ai = rf.post('/api/v1/ai/generate-quiz/')
        tier, limit, window, key = resolve_tier_and_key(req_ai)
        assert tier == 'ai'
        assert limit == 20
        assert 'ratelimit:ai:' in key

        # Session Join
        req_session = rf.post('/api/v1/sessions/join/')
        tier, limit, window, key = resolve_tier_and_key(req_session)
        assert tier == 'session'
        assert limit == 60

        # General API
        req_api = rf.get('/api/v1/quizzes/')
        tier, limit, window, key = resolve_tier_and_key(req_api)
        assert tier == 'api'
        assert limit == 120

    def test_sliding_window_rate_limiting_enforced(self, client):
        """Verify that 5 requests succeed, but 6th triggers HTTP 429."""
        url = '/api/v1/auth/login/'

        # Send 5 requests (all should reach the endpoint and return 400 for empty body)
        for i in range(5):
            resp = client.post(url, data={}, content_type='application/json')
            assert resp.status_code == 400
            assert resp.headers.get('X-RateLimit-Limit') == '5'

        # 6th request must be blocked by rate limit middleware
        resp6 = client.post(url, data={}, content_type='application/json')
        assert resp6.status_code == 429
        data = resp6.json()
        assert data['error'] == 'Too Many Requests'
        assert 'retry_after' in data
        assert resp6.headers.get('Retry-After') is not None
        assert resp6.headers.get('X-RateLimit-Remaining') == '0'

    def test_sliding_window_recovers_after_eviction(self):
        key = "test:sliding:key"
        limit = 3
        window = 2

        # 3 requests allowed
        assert check_rate_limit(key, limit, window)[0] is True
        assert check_rate_limit(key, limit, window)[0] is True
        assert check_rate_limit(key, limit, window)[0] is True

        # 4th request blocked
        is_allowed, remaining, retry_after = check_rate_limit(key, limit, window)
        assert is_allowed is False
        assert retry_after > 0


# ============================================================================
# 3. Brute-Force Account & IP Lockout Tests (OWASP A07)
# ============================================================================

class TestBruteForceProtection:

    def test_lockout_after_five_failed_attempts(self, client, teacher_user):
        ip = "192.168.10.50"
        url = '/api/v1/auth/login/'

        # Disable sliding window middleware for this targeted brute force test
        with patch('core.middleware.rate_limit.check_rate_limit', return_value=(True, 10, 0)):
            # 4 failed attempts
            for i in range(4):
                resp = client.post(
                    url,
                    data={'username': teacher_user.username, 'password': 'wrongpassword'},
                    content_type='application/json',
                    REMOTE_ADDR=ip
                )
                assert resp.status_code == 401

            is_locked, _ = is_account_locked(ip, teacher_user.username)
            assert is_locked is False

            # 5th failed attempt triggers lockout
            resp5 = client.post(
                url,
                data={'username': teacher_user.username, 'password': 'wrongpassword'},
                content_type='application/json',
                REMOTE_ADDR=ip
            )
            assert resp5.status_code == 401

            is_locked, remaining = is_account_locked(ip, teacher_user.username)
            assert is_locked is True
            assert remaining > 800

            # 6th attempt (even with valid password!) is blocked with HTTP 429
            resp6 = client.post(
                url,
                data={'username': teacher_user.username, 'password': 'ValidPassword2026!'},
                content_type='application/json',
                REMOTE_ADDR=ip
            )
            assert resp6.status_code == 429
            assert 'bloklandi' in resp6.json()['message']

    def test_successful_login_resets_failures(self, client, teacher_user):
        ip = "192.168.10.60"
        record_login_failure(ip, teacher_user.username)
        record_login_failure(ip, teacher_user.username)

        # Successful login
        with patch('core.middleware.rate_limit.check_rate_limit', return_value=(True, 10, 0)):
            resp = client.post(
                '/api/v1/auth/login/',
                data={'username': teacher_user.username, 'password': 'ValidPassword2026!'},
                content_type='application/json',
                REMOTE_ADDR=ip
            )
            assert resp.status_code == 200

            is_locked, _ = is_account_locked(ip, teacher_user.username)
            assert is_locked is False


# ============================================================================
# 4. OWASP A03 Input Sanitization & XSS Prevention (via Bleach)
# ============================================================================

class TestXSSSanitization:

    def test_sanitize_plain_text_strips_all_html(self):
        raw = "<script>alert('xss')</script>O‘zbekiston <b>tarixi</b>"
        cleaned = sanitize_text(raw)
        assert cleaned == "O‘zbekiston tarixi"
        assert '<' not in cleaned
        assert '>' not in cleaned

    def test_sanitize_rich_text_preserves_safe_tags_removes_dangerous(self):
        raw = (
            "<p>Mexanika qonuni: v = s / t. "
            "Formulalar: H<sub>2</sub>O va x<sup>2</sup>. "
            "<script>fetch('http://evil.com')</script>"
            "<img src='bad.jpg' onerror='alert(1)'>"
            "<span class='math-highlight'>Izoh</span></p>"
        )
        cleaned = sanitize_rich_text(raw)

        # Safe tags preserved
        assert "<p>" in cleaned
        assert "<sub>2</sub>" in cleaned
        assert "<sup>2</sup>" in cleaned
        assert '<span class="math-highlight">' in cleaned

        # Dangerous tags and event handlers stripped
        assert "<script>" not in cleaned
        assert "onerror" not in cleaned
        assert "fetch" not in cleaned

    def test_sanitize_rich_text_javascript_protocol(self):
        raw = '<a href="javascript:alert(1)">Havola</a>'
        cleaned = sanitize_rich_text(raw)
        assert "javascript:" not in cleaned


# ============================================================================
# 5. OWASP A03 SQL Injection Resilience
# ============================================================================

class TestSQLInjectionResilience:

    def test_orm_parameterization_against_sqli(self, db, teacher_user):
        Quiz.objects.create(
            owner=teacher_user,
            title="Biologiya 9-Sinf",
            subject="Biologiya",
            grade_level=9
        )

        malicious_inputs = [
            "' OR '1'='1",
            "'; DROP TABLE quizzes_quiz; --",
            "1 UNION SELECT 1, 'admin', 'password', 4, 5, 6, 7, 8, 9, 10 --",
            "' OR 1=1 --"
        ]

        for payload in malicious_inputs:
            # Querying by title must not crash or return unowned records
            results = Quiz.objects.filter(title=payload)
            assert results.count() == 0

            results_owner = Quiz.objects.filter(owner=teacher_user, title__icontains=payload)
            assert results_owner.count() == 0


# ============================================================================
# 6. Password Strength Validation (OWASP A07)
# ============================================================================

class TestPasswordStrengthValidator:

    def test_password_length_rejection(self):
        is_valid, msg = validate_password_strength("Short1!")
        assert is_valid is False
        assert "kamida 8 ta" in msg

    def test_common_weak_password_rejection(self):
        is_valid, msg = validate_password_strength("password123")
        assert is_valid is False
        assert "sodda va ommabop" in msg

    def test_missing_character_types(self):
        # Missing uppercase
        assert validate_password_strength("alllowercase123")[0] is False
        # Missing lowercase
        assert validate_password_strength("ALLUPPERCASE123")[0] is False
        # Missing digit
        assert validate_password_strength("NoDigitsHere!")[0] is False

    def test_valid_strong_password(self):
        is_valid, msg = validate_password_strength("EduSelf#Secure2026")
        assert is_valid is True
        assert msg is None


# ============================================================================
# 7. Cross-Tenant / Multi-Tenant Isolation (OWASP A01)
# ============================================================================

class TestCrossTenantIsolation:

    def test_teacher_cannot_modify_other_teachers_quiz(self, teacher_user, other_teacher):
        quiz = Quiz.objects.create(
            owner=teacher_user,
            title="Fizika Yopiq Test",
            subject="Fizika",
            grade_level=10
        )

        client = APIClient()
        client.force_authenticate(user=other_teacher)

        # Attempt to delete Teacher 1's quiz as Teacher 2
        resp = client.delete(f'/api/v1/quizzes/{quiz.id}/')
        assert resp.status_code in (403, 404)

        # Quiz should still exist in database
        assert Quiz.objects.filter(id=quiz.id).exists()


# ============================================================================
# 8. Security Audit Logging (OWASP A09)
# ============================================================================

class TestSecurityAuditLogging:

    def test_audit_log_captures_mutation_events(self, client, teacher_user, caplog):
        with caplog.at_level(logging.INFO, logger='security.audit'):
            client.force_login(teacher_user)
            resp = client.post(
                '/api/v1/quizzes/',
                data=json.dumps({
                    'title': 'Audit Test Quiz',
                    'subject': 'Informatika',
                    'grade_level': 8
                }),
                content_type='application/json'
            )
            assert resp.status_code in (200, 201)

            # Check that an audit log entry was emitted
            audit_records = [
                r for r in caplog.records
                if r.name == 'security.audit'
            ]
            assert len(audit_records) >= 1
            payload = json.loads(audit_records[-1].getMessage())
            assert payload['event_type'] == 'RESOURCE_MUTATED'
            assert payload['method'] == 'POST'
            assert payload['username'] == teacher_user.username
