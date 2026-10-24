import os
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from django.conf import settings


def get_default_master_key() -> bytes:
    """Retrieves 32-byte master key from settings or environment."""
    key = getattr(settings, "BYOK_MASTER_KEY", None)
    if isinstance(key, str):
        key = key.encode("utf-8")
    if not key:
        key = b"eduself-teacher-byok-aes256gcm!"
    return key[:32].ljust(32, b"0")


def mask_api_key(api_key: str) -> str:
    """
    Masks API key for safe frontend display (DOC-77 Section 2 & 4).
    Example: 'sk-proj-1234567890abcdef' -> 'sk-proj-...cdef'
    """
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    if api_key.startswith("sk-") and len(api_key) >= 16:
        prefix = api_key[:8]
        suffix = api_key[-4:]
        return f"{prefix}...{suffix}"
    return f"{api_key[:4]}...{api_key[-4:]}"


class AESGCMCipher:
    """
    AES-256-GCM symmetric encryption utility for BYOK API credentials.
    Implements DOC-77 (BYOK.md).
    """

    @classmethod
    def encrypt(
        cls,
        plain_text: str,
        master_key: Optional[bytes] = None,
        associated_data: Optional[bytes] = None,
    ) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypts plaintext with AES-256-GCM.
        Returns (ciphertext, iv, auth_tag).
        - iv: 12-byte random initialization vector
        - auth_tag: 16-byte GCM authentication tag
        """
        key = master_key or get_default_master_key()
        if len(key) != 32:
            raise ValueError(f"AES-256 master key must be exactly 32 bytes (got {len(key)} bytes).")

        iv = os.urandom(12)
        aesgcm = AESGCM(key)
        data = plain_text.encode("utf-8")

        # AESGCM.encrypt produces ciphertext + 16-byte tag
        ct_with_tag = aesgcm.encrypt(iv, data, associated_data)
        ciphertext = ct_with_tag[:-16]
        auth_tag = ct_with_tag[-16:]

        return ciphertext, iv, auth_tag

    @classmethod
    def decrypt(
        cls,
        ciphertext: bytes,
        iv: bytes,
        auth_tag: bytes,
        master_key: Optional[bytes] = None,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """
        Decrypts ciphertext with AES-256-GCM.
        Raises InvalidTag if ciphertext, IV, or auth_tag is tampered with.
        """
        key = master_key or get_default_master_key()
        if len(key) != 32:
            raise ValueError(f"AES-256 master key must be exactly 32 bytes (got {len(key)} bytes).")

        aesgcm = AESGCM(key)
        ct_with_tag = ciphertext + auth_tag
        decrypted_bytes = aesgcm.decrypt(iv, ct_with_tag, associated_data)
        return decrypted_bytes.decode("utf-8")
