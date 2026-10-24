"""
Authentication and Input Security Services according to DOC-SEC-01 (SECURITY.md).
Provides Brute-Force lockout, Password strength validation, and HTML/XSS sanitization via bleach.
"""

import re
import bleach
import logging
from typing import Optional, Tuple
from django.core.cache import cache

logger = logging.getLogger("authentication.security")

# Ruxsat etilgan xavfsiz HTML teglari (faqat formatlash uchun)
ALLOWED_TAGS = [
    "b", "i", "u", "em", "strong", "p", "br",
    "ul", "ol", "li", "span", "sub", "sup", "code",
]

ALLOWED_ATTRIBUTES = {
    "span": ["class"],
    "code": ["class"],
}

LOCKOUT_THRESHOLD = 5         # 5 ta xato urinishdan so'ng bloklanadi
LOCKOUT_DURATION_SECONDS = 900  # 15 daqiqa (15 * 60)


def sanitize_html(html_content: Optional[str]) -> str:
    """
    Foydalanuvchi yoki AI kiritgan matndagi xavfli skriptlarni (XSS) tozalash.
    <script>, <iframe>, <style>, onload/onerror hodisalarini va ularning ichki
    kodlarini to'liq olib tashlaydi.
    """
    if not html_content:
        return ""

    # Dastlab xavfli blokli teglarni ichki kodi bilan birga tozalash
    stripped = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*>.*?</\1>", "", str(html_content))
    # Yopilmagan yoki noto'g'ri teglarni ham tozalash
    stripped = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*>", "", stripped)

    cleaned = bleach.clean(
        stripped,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,  # Xavfli teglarni qoldiqsiz o'chirish
    )
    return cleaned.strip()


def sanitize_plain_text(text: Optional[str]) -> str:
    """
    Barcha HTML teglarni butunlay tozalab, faqat xavfsiz oddiy matn qoldirish.
    """
    if not text:
        return ""

    stripped = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*>.*?</\1>", "", str(text))
    cleaned = bleach.clean(
        stripped,
        tags=[],
        strip=True,
    )
    # Xavfli boshqaruv belgilarini tozalash
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", cleaned)
    return cleaned.strip()


class AccountLockoutManager:
    """
    Brute-force (parolni tanlash) hujumlariga qarshi himoya menejeri.
    5 marta xato parol kiritilsa, foydalanuvchi va IP 15 daqiqaga bloklanadi.
    """

    @classmethod
    def _ip_key(cls, ip: str) -> str:
        return f"lockout:ip:{ip}"

    @classmethod
    def _user_key(cls, identifier: str) -> str:
        return f"lockout:user:{identifier}"

    @classmethod
    def is_locked(cls, identifier: str, ip: str) -> Tuple[bool, int]:
        """
        Foydalanuvchi yoki IP bloklanganligini tekshirish.
        (is_locked, remaining_seconds) qaytaradi.
        """
        user_key = cls._user_key(identifier)
        ip_key = cls._ip_key(ip)

        user_attempts = cache.get(user_key) or 0
        ip_attempts = cache.get(ip_key) or 0

        if user_attempts >= LOCKOUT_THRESHOLD or ip_attempts >= LOCKOUT_THRESHOLD:
            # Qolgan vaqtni hisoblash
            ttl = cache.ttl(user_key) if hasattr(cache, "ttl") else LOCKOUT_DURATION_SECONDS
            return True, max(1, ttl if isinstance(ttl, int) and ttl > 0 else LOCKOUT_DURATION_SECONDS)

        return False, 0

    @classmethod
    def record_failed_attempt(cls, identifier: str, ip: str) -> int:
        """
        Xato urinishni qayd qilish va urinishlar sonini oshirish.
        """
        user_key = cls._user_key(identifier)
        ip_key = cls._ip_key(ip)

        current_user_fails = cache.get(user_key) or 0
        new_user_fails = current_user_fails + 1
        cache.set(user_key, new_user_fails, timeout=LOCKOUT_DURATION_SECONDS)

        current_ip_fails = cache.get(ip_key) or 0
        new_ip_fails = current_ip_fails + 1
        cache.set(ip_key, new_ip_fails, timeout=LOCKOUT_DURATION_SECONDS)

        logger.warning(
            f"Failed login attempt for {identifier} from {ip}. "
            f"Fails count: {new_user_fails}/{LOCKOUT_THRESHOLD}"
        )

        if new_user_fails >= LOCKOUT_THRESHOLD or new_ip_fails >= LOCKOUT_THRESHOLD:
            logger.error(f"Account/IP locked out due to multiple failed logins: {identifier} / {ip}")

        return max(new_user_fails, new_ip_fails)

    @classmethod
    def reset_attempts(cls, identifier: str, ip: str) -> None:
        """
        Muvaffaqiyatli kirishdan so'ng urinishlar hisoblagichini tozalash.
        """
        cache.delete(cls._user_key(identifier))
        cache.delete(cls._ip_key(ip))


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Parol mustahkamligini tekshirish (NIST va OWASP tavsiyalari).
    - Kamida 8 ta belgi
    - Kamida bitta raqam
    - Kamida bitta harf
    - Keng tarqalgan oson parollarga kirmasligi
    """
    if not password or len(password) < 8:
        return False, "Parol kamida 8 ta belgidan iborat bo'lishi kerak."

    if not re.search(r"\d", password):
        return False, "Parolda kamida bitta raqam bo'lishi shart."

    if not re.search(r"[a-zA-Z]", password):
        return False, "Parolda kamida bitta harf bo'lishi shart."

    common_passwords = {
        "12345678", "password", "qwerty123", "admin123", "password123",
        "eduself123", "teacher123", "123456789"
    }
    if password.lower() in common_passwords:
        return False, "Bu parol juda keng tarqalgan va oson taxmin qilinadi."

    return True, None
