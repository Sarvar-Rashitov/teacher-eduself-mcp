# apps/authentication/security.py
"""
Security Utilities: Brute Force Protection, XSS Sanitizer, Prompt Injection Guard.
SECURITY.md §3, §6 va AI_SECURITY.md asosida.
"""
import time
import re
import bleach
from typing import Tuple, Optional
from django.core.cache import cache

# ============================================================
# 1. Brute Force Protection (SECURITY.md §3)
# ============================================================
class BruteForceProtector:
    """
    Login urinishlari bo'yicha Brute-force himoyasi.
    5 marta ketma-ket xato parol kiritilganda IP yoki foydalanuvchini 15 daqiqaga bloklaydi.
    """
    MAX_ATTEMPTS = 5
    LOCKOUT_SECONDS = 900  # 15 daqiqa

    @classmethod
    def get_attempts_key(cls, identifier: str) -> str:
        return f"failed_login_attempts_{identifier}"

    @classmethod
    def get_lockout_key(cls, identifier: str) -> str:
        return f"lockout_{identifier}"

    @classmethod
    def is_locked(cls, identifier: str) -> Tuple[bool, int]:
        """
        Foydalanuvchi yoki IP bloklanganligini tekshirish.
        (is_locked, remaining_seconds) qaytaradi.
        """
        lock_key = cls.get_lockout_key(identifier)
        lock_until = cache.get(lock_key)
        if lock_until:
            now = time.time()
            if lock_until > now:
                return True, int(lock_until - now)
            cache.delete(lock_key)
        return False, 0

    @classmethod
    def record_failed_attempt(cls, identifier: str) -> Tuple[int, bool]:
        """
        Muvaffaqiyatsiz urinishni qayd etish.
        (current_attempts, is_now_locked) qaytaradi.
        """
        is_locked_now, _ = cls.is_locked(identifier)
        if is_locked_now:
            return cls.MAX_ATTEMPTS, True

        att_key = cls.get_attempts_key(identifier)
        attempts = cache.get(att_key, 0) + 1
        cache.set(att_key, attempts, timeout=cls.LOCKOUT_SECONDS)

        if attempts >= cls.MAX_ATTEMPTS:
            # 15 daqiqaga bloklash
            lock_until = time.time() + cls.LOCKOUT_SECONDS
            cache.set(cls.get_lockout_key(identifier), lock_until, timeout=cls.LOCKOUT_SECONDS)
            return attempts, True

        return attempts, False

    @classmethod
    def reset_attempts(cls, identifier: str):
        """Muvaffaqiyatli kirishda hisoblagich va blokirovkali kalitlarni tozalash."""
        cache.delete(cls.get_attempts_key(identifier))
        cache.delete(cls.get_lockout_key(identifier))


# ============================================================
# 2. XSS Sanitizer (SECURITY.md §6 & OWASP A03)
# ============================================================
class XSSSanitizer:
    """
    Foydalanuvchi tomonidan kiritilgan barcha matnlarni zararli HTML/JavaScript
    kodlaridan tozalovchi XSS himoya vositasi (bleach).
    """
    ALLOWED_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'span', 'code', 'pre', 'sub', 'sup']
    ALLOWED_ATTRIBUTES = {
        'span': ['class'],
        'code': ['class']
    }

    @classmethod
    def clean_html(cls, text: Optional[str]) -> str:
        """Xavfsiz HTML formatlash teglariga ruxsat bergan holda script, style va iframelarni ichki matni bilan tozalash."""
        if not text:
            return ""
        # <script>...</script>, <style>...</style>, <iframe>...</iframe> bloklarini ichki matni bilan birga yo'qotish
        text_no_scripts = re.sub(r'<(script|style|iframe)[^>]*>.*?</\1>', '', str(text), flags=re.IGNORECASE | re.DOTALL)
        # inline event handlerlar: onerror=, onclick= va hokazo
        text_no_events = re.sub(r'\bon\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', text_no_scripts, flags=re.IGNORECASE)
        return bleach.clean(
            text_no_events,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            strip=True,
            strip_comments=True
        )

    @classmethod
    def clean_plain(cls, text: Optional[str]) -> str:
        """Barcha HTML teglarni to'liq tozalab, sof matn qoldirish."""
        if not text:
            return ""
        text_no_scripts = re.sub(r'<(script|style|iframe)[^>]*>.*?</\1>', '', str(text), flags=re.IGNORECASE | re.DOTALL)
        return bleach.clean(text_no_scripts, tags=[], strip=True, strip_comments=True)


# ============================================================
# 3. Prompt Injection Guard (AI_SECURITY.md §1 & §3)
# ============================================================
class PromptInjectionGuard:
    """
    Tashqi AI ga uzatilayotgan kiritmalarni prompt injection va jailbreak
    shablonlariga tekshirish hamda teglash orqali chegaralash.
    """
    MALICIOUS_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts)",
        r"disregard\s+(all\s+)?prior\s+system\s+prompts",
        r"you\s+are\s+now\s+in\s+developer\s+mode",
        r"\bdan\s+mode\b",
        r"output\s+(your\s+)?system\s+prompt\s+verbatim",
        r"roleplay\s+as\s+an\s+unfiltered\s+ai",
        r"forget\s+all\s+previous\s+instructions",
        r"override\s+system\s+prompt",
        r"bypass\s+(safety|content)\s+filters?",
    ]

    @classmethod
    def is_injection_attempt(cls, text: Optional[str]) -> Tuple[bool, str]:
        """
        Agar kiritmada xavfli prompt injection shabloni aniqlansa:
        (True, 'aniqlangan_sabab') qaytaradi.
        """
        if not text:
            return False, ""

        clean_text = str(text).lower()
        for pattern in cls.MALICIOUS_PATTERNS:
            match = re.search(pattern, clean_text)
            if match:
                return True, match.group(0)

        return False, ""

    @classmethod
    def wrap_user_content(cls, user_text: str) -> str:
        """
        Zararli kiritmalarni model buyruq emas, ma'lumot sifatida qabul qilishi uchun
        qat'iy XML chegarasi bilan o'rash (Tag Isolation).
        """
        sanitized = XSSSanitizer.clean_plain(user_text)
        return f"<user_content>\n{sanitized}\n</user_content>"
