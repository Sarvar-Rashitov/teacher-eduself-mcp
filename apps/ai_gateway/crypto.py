"""
AES-256-GCM BYOK Shifrlash Moduli.
Spetsifikatsiya: .docs/ai/BYOK.md
"""
import os
import hashlib
from typing import Tuple, Optional
from django.conf import settings
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag


class DecryptionError(Exception):
    """Shifrlangan kalitni ochishda yaxlitlik tekshiruvi xatosi."""
    pass


def get_master_key() -> bytes:
    """
    Platformaning 32 baytlik Master shifrlash kalitini olish.
    Agar BYOK_ENCRYPTION_KEY ko'rsatilgan bo'lsa uni,
    aks holda SECRET_KEY dan SHA-256 orqali deterministik 32 bayt kalit olinadi.
    """
    configured_key = getattr(settings, 'BYOK_ENCRYPTION_KEY', None)
    if configured_key:
        if isinstance(configured_key, bytes) and len(configured_key) == 32:
            return configured_key
        key_str = str(configured_key).strip()
        if len(key_str) == 64:  # Hex-encoded 32 bytes
            try:
                return bytes.fromhex(key_str)
            except ValueError:
                pass
        return hashlib.sha256(key_str.encode('utf-8')).digest()

    secret = getattr(settings, 'SECRET_KEY', 'default-eduself-byok-secret')
    return hashlib.sha256(secret.encode('utf-8')).digest()


def mask_api_key(plain_key: str) -> str:
    """
    Frontend va loglar uchun API kalitni xavfsiz niqoblash.
    Namuna: 'sk-proj-123456789abcdef' -> 'sk-proj-...cdef'
    """
    if not plain_key:
        return ""
    clean = plain_key.strip()
    if len(clean) <= 8:
        return f"...{clean[-2:]}" if len(clean) >= 2 else "..."

    # Agar 'sk-' yoki 'sk-proj-' kabi prefiks bo'lsa uni saqlab qolamiz
    if clean.startswith("sk-proj-"):
        prefix = "sk-proj-"
    elif clean.startswith("sk-"):
        prefix = "sk-"
    elif clean.startswith("AIza"):
        prefix = "AIza"
    else:
        prefix = clean[:4]

    suffix = clean[-4:]
    return f"{prefix}...{suffix}"


def encrypt_api_key(
    plain_key: str,
    master_key: Optional[bytes] = None
) -> Tuple[bytes, bytes, bytes, str]:
    """
    API kalitni AES-256-GCM bilan shifrlash.
    Qaytaradi: (encrypted_data, iv, auth_tag, masked_key)
    - iv: 12 bayt
    - auth_tag: 16 bayt
    - encrypted_data: binary shifrlangan ma'lumot
    - masked_key: xavfsiz matn
    """
    if not plain_key:
        raise ValueError("Shifrlash uchun API kalit bo'sh bo'lishi mumkin emas.")

    key = master_key or get_master_key()
    aesgcm = AESGCM(key)

    # 12 baytlik unikal IV (Initialization Vector)
    iv = os.urandom(12)
    plaintext_bytes = plain_key.strip().encode('utf-8')

    # AESGCM.encrypt ciphertext + 16 baytlik tag qaytaradi
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext_bytes, None)

    encrypted_data = ciphertext_with_tag[:-16]
    auth_tag = ciphertext_with_tag[-16:]
    masked = mask_api_key(plain_key)

    return encrypted_data, iv, auth_tag, masked


def decrypt_api_key(
    encrypted_data: bytes,
    iv: bytes,
    auth_tag: bytes,
    master_key: Optional[bytes] = None
) -> str:
    """
    Shifrlangan kalitni AES-256-GCM orqali ochish.
    Agar kalit soxtalashtirilgan yoki buzilgan bo'lsa, DecryptionError qo'zg'atadi.
    """
    key = master_key or get_master_key()
    aesgcm = AESGCM(key)

    ciphertext_with_tag = encrypted_data + auth_tag

    try:
        decrypted_bytes = aesgcm.decrypt(iv, ciphertext_with_tag, None)
        return decrypted_bytes.decode('utf-8')
    except (InvalidTag, ValueError) as e:
        raise DecryptionError("Shifrlangan kalit yaxlitligi buzilgan yoki autentifikatsiya tegi mos kelmadi.") from e
