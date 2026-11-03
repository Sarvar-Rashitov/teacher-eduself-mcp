"""
Security Utilities for EduSelf Authentication & Input Protection (Phase 10).
Includes:
1. Brute-force Login Failure Tracking & Account/IP Lockout
2. OWASP A03 XSS Input Sanitization (via Bleach)
3. Password Complexity and Common Blacklist Validator
"""

import re
import time
from typing import Dict, Optional, Tuple

import bleach
from django.core.cache import cache


# Configuration for Brute-force Protection
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15 minutes lockout

# In-memory storage for test/fallback environments
_in_memory_failed_attempts: Dict[str, list] = {}
_in_memory_lockouts: Dict[str, float] = {}

# Common weak passwords blacklist
COMMON_WEAK_PASSWORDS = {
    '12345678', 'password', 'password123', 'admin123', 'qwerty123',
    'eduself123', 'teacher123', 'iloveyou', 'welcome1', '123456789'
}

# Allowed HTML tags and attributes for rich text (e.g. quiz explanations, math notation)
ALLOWED_RICH_TAGS = [
    'b', 'i', 'u', 'em', 'strong', 'code', 'pre',
    'p', 'br', 'ul', 'ol', 'li', 'span', 'sub', 'sup'
]
ALLOWED_RICH_ATTRIBUTES = {
    'span': ['class'],
    'code': ['class'],
}


# ============================================================================
# 1. Brute-force Lockout Manager
# ============================================================================

def _get_lockout_keys(ip: str, username: Optional[str] = None) -> list:
    """Generates cache keys for IP and optional username tracking."""
    keys = [f"lockout:ip:{ip}"]
    if username:
        cleaned_user = username.strip().lower()
        keys.append(f"lockout:user:{cleaned_user}")
    return keys


def is_account_locked(ip: str, username: Optional[str] = None) -> Tuple[bool, int]:
    """
    Checks if an IP or username is currently locked out due to excessive failed attempts.
    Returns (is_locked, seconds_remaining).
    """
    now = time.time()
    keys = _get_lockout_keys(ip, username)

    for key in keys:
        try:
            lock_until = cache.get(f"{key}:locked")
            if lock_until and float(lock_until) > now:
                return True, int(float(lock_until) - now)
        except Exception:
            pass

        # In-memory fallback check
        mem_lock = _in_memory_lockouts.get(f"{key}:locked", 0)
        if mem_lock > now:
            return True, int(mem_lock - now)

    return False, 0


def record_login_failure(ip: str, username: Optional[str] = None) -> int:
    """
    Records a failed login attempt for the given IP and optional username.
    If attempts reach MAX_LOGIN_ATTEMPTS, locks the target for LOCKOUT_DURATION_SECONDS.
    Returns current failure count.
    """
    now = time.time()
    keys = _get_lockout_keys(ip, username)
    max_count = 0

    for key in keys:
        attempts_key = f"{key}:attempts"
        count = 1

        try:
            val = cache.get(attempts_key)
            if val is not None:
                count = int(val) + 1
            cache.set(attempts_key, count, timeout=LOCKOUT_DURATION_SECONDS)
        except Exception:
            # In-memory fallback
            times = _in_memory_failed_attempts.setdefault(attempts_key, [])
            cutoff = now - LOCKOUT_DURATION_SECONDS
            times = [t for t in times if t > cutoff]
            times.append(now)
            _in_memory_failed_attempts[attempts_key] = times
            count = len(times)

        max_count = max(max_count, count)

        if count >= MAX_LOGIN_ATTEMPTS:
            lock_until = now + LOCKOUT_DURATION_SECONDS
            try:
                cache.set(f"{key}:locked", lock_until, timeout=LOCKOUT_DURATION_SECONDS)
            except Exception:
                pass
            _in_memory_lockouts[f"{key}:locked"] = lock_until

    return max_count


def reset_login_failures(ip: str, username: Optional[str] = None):
    """Resets failed login counters and clears lockouts upon successful authentication."""
    keys = _get_lockout_keys(ip, username)

    for key in keys:
        try:
            cache.delete(f"{key}:attempts")
            cache.delete(f"{key}:locked")
        except Exception:
            pass

        _in_memory_failed_attempts.pop(f"{key}:attempts", None)
        _in_memory_lockouts.pop(f"{key}:locked", None)


# ============================================================================
# 2. OWASP A03 XSS Input Sanitization
# ============================================================================

SCRIPT_BLOCK_PATTERN = re.compile(
    r'<(script|style|iframe|object|embed)[^>]*>[\s\S]*?</\1>',
    re.IGNORECASE
)


def sanitize_text(text: Optional[str]) -> str:
    """
    Strips ALL HTML tags and dangerous characters from plain text inputs (e.g. titles, usernames).
    Prevents Stored and Reflected XSS attacks.
    """
    if not text:
        return ""
    # Strip script/style blocks entirely
    stripped = SCRIPT_BLOCK_PATTERN.sub('', str(text))
    cleaned = bleach.clean(
        stripped,
        tags=[],
        attributes={},
        strip=True
    )
    return cleaned.strip()


def sanitize_rich_text(html: Optional[str]) -> str:
    """
    Cleans rich text (e.g. question prompts, mathematical explanations).
    Permits strictly safe formatting tags while stripping script, iframe, onload, javascript: protocols.
    """
    if not html:
        return ""

    # Strip script/style blocks entirely
    stripped = SCRIPT_BLOCK_PATTERN.sub('', str(html))
    cleaned = bleach.clean(
        stripped,
        tags=ALLOWED_RICH_TAGS,
        attributes=ALLOWED_RICH_ATTRIBUTES,
        protocols=['http', 'https', 'mailto'],
        strip=True
    )
    return cleaned.strip()


# ============================================================================
# 3. Password Strength Validator
# ============================================================================

def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validates password strength according to OWASP A07 recommendations:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - Not in common weak passwords blacklist
    Returns (is_valid, error_message).
    """
    if not password or len(password) < 8:
        return False, "Parol kamida 8 ta belgidan iborat bo‘lishi kerak."

    if password.lower() in COMMON_WEAK_PASSWORDS:
        return False, "Ushbu parol juda sodda va ommabop. Iltimos, murakkabroq parol tanlang."

    if not re.search(r'[A-Z]', password):
        return False, "Parolda kamida bitta katta harf (A-Z) bo‘lishi shart."

    if not re.search(r'[a-z]', password):
        return False, "Parolda kamida bitta kichik harf (a-z) bo‘lishi shart."

    if not re.search(r'\d', password):
        return False, "Parolda kamida bitta raqam (0-9) bo‘lishi shart."

    return True, None
