import os
import hashlib
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


def get_master_key() -> bytes:
    """
    Retrieve 32-byte (256-bit) encryption key from Django settings or environment.
    Uses SHA-256 derivation to guarantee exactly 32 bytes regardless of input format.
    """
    raw_key = getattr(
        settings,
        "BYOK_ENCRYPTION_KEY",
        os.getenv("BYOK_ENCRYPTION_KEY", "eduself-byok-default-secret-encryption-master-key-32b"),
    )
    if isinstance(raw_key, str):
        raw_key = raw_key.encode("utf-8")
    return hashlib.sha256(raw_key).digest()


def mask_key(plain_key: str) -> str:
    """
    DOC-77 Section 2: Mask API key for frontend safe presentation.
    Example: 'sk-proj-abcdef1234567890' -> 'sk-proj-...7890'
    """
    if not plain_key or len(plain_key) <= 8:
        return "****"

    if "-" in plain_key:
        prefix, rest = plain_key.split("-", 1)
        prefix = f"{prefix}-"
    else:
        prefix = plain_key[:4]

    suffix = plain_key[-4:]
    return f"{prefix}...{suffix}"


def encrypt_api_key(
    plain_key: str,
    master_key: Optional[bytes] = None,
) -> Tuple[bytes, bytes, bytes, str]:
    """
    Encrypts plain API key using AES-256-GCM.
    Returns: (encrypted_key, iv, auth_tag, masked_key)
    """
    key = master_key or get_master_key()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)  # 96-bit standard GCM nonce
    data = plain_key.encode("utf-8")

    # AESGCM.encrypt returns ciphertext + 16-byte tag appended
    encrypted_blob = aesgcm.encrypt(iv, data, None)
    ciphertext = encrypted_blob[:-16]
    auth_tag = encrypted_blob[-16:]
    masked = mask_key(plain_key)

    return ciphertext, iv, auth_tag, masked


def decrypt_api_key(
    ciphertext: bytes,
    iv: bytes,
    auth_tag: bytes,
    master_key: Optional[bytes] = None,
) -> str:
    """
    Decrypts AES-256-GCM ciphertext and verifies integrity using auth_tag.
    Raises InvalidTag if ciphertext or tag was tampered with.
    """
    key = master_key or get_master_key()
    aesgcm = AESGCM(key)
    payload = bytes(ciphertext) + bytes(auth_tag)
    decrypted_bytes = aesgcm.decrypt(bytes(iv), payload, None)
    return decrypted_bytes.decode("utf-8")
