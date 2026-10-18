"""
BYOK AES-256-GCM Encryption, Decryption, and Key Masking Utilities.

This module provides authenticated encryption using AES-256-GCM to ensure:
- Confidentiality: Plaintext API keys are never stored on disk or in logs.
- Integrity: 16-byte GCM authentication tag guarantees tamper resistance.
- Freshness: Unique 12-byte random Initialization Vector (IV) for every encryption.
"""

import hashlib
import os
from typing import Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
from django.conf import settings


class DecryptionError(Exception):
    """Raised when decryption fails due to invalid key, tampered data, or corrupted auth tag."""
    pass


def get_encryption_master_key() -> bytes:
    """
    Derives a 32-byte (256-bit) master encryption key.
    Uses BYOK_ENCRYPTION_KEY if set, otherwise falls back to SECRET_KEY.
    Applies SHA-256 to ensure exact 32-byte key length.
    """
    raw_key = getattr(settings, 'BYOK_ENCRYPTION_KEY', None)
    if not raw_key:
        raw_key = getattr(settings, 'SECRET_KEY', 'default-eduself-insecure-key-32bytes')
    
    if isinstance(raw_key, str):
        raw_bytes = raw_key.encode('utf-8')
    else:
        raw_bytes = bytes(raw_key)
        
    return hashlib.sha256(raw_bytes).digest()


def mask_api_key(plain_key: str) -> str:
    """
    Masks an API key for safe frontend display and audit logging.
    Example:
        'sk-proj-1234567890abcdef' -> 'sk-proj-...cdef'
        'AIzaSyB1234567890xyz' -> 'AIza...0xyz'
    """
    if not plain_key:
        return ""
    
    clean_key = plain_key.strip()
    length = len(clean_key)
    
    if length <= 8:
        return clean_key[:2] + "..." + clean_key[-2:] if length >= 4 else "****"
    
    # Check known prefixes
    if clean_key.startswith("sk-proj-"):
        prefix_len = 8
    elif clean_key.startswith("sk-ant-"):
        prefix_len = 7
    elif clean_key.startswith("sk-"):
        prefix_len = 3
    elif clean_key.startswith("AIza"):
        prefix_len = 4
    else:
        prefix_len = min(4, max(2, length // 3))

    suffix_len = min(4, max(2, length // 4))
    
    return f"{clean_key[:prefix_len]}...{clean_key[-suffix_len:]}"


def encrypt_api_key(plain_key: str, master_key: bytes = None) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypts a plaintext API key using AES-256-GCM.
    
    Args:
        plain_key: Plaintext string representation of the API key.
        master_key: Optional 32-byte key (uses get_encryption_master_key() if None).
        
    Returns:
        Tuple of (encrypted_key: bytes, iv: bytes, auth_tag: bytes)
    """
    if not plain_key:
        raise ValueError("Cannot encrypt an empty API key.")
    
    key = master_key or get_encryption_master_key()
    aesgcm = AESGCM(key)
    
    # Generate unique 12-byte (96-bit) IV for GCM
    iv = os.urandom(12)
    data = plain_key.strip().encode('utf-8')
    
    # AESGCM.encrypt returns ciphertext + 16-byte authentication tag appended
    ciphertext_with_tag = aesgcm.encrypt(iv, data, None)
    
    encrypted_key = ciphertext_with_tag[:-16]
    auth_tag = ciphertext_with_tag[-16:]
    
    return encrypted_key, iv, auth_tag


def decrypt_api_key(encrypted_key: bytes, iv: bytes, auth_tag: bytes, master_key: bytes = None) -> str:
    """
    Decrypts an AES-256-GCM encrypted API key and verifies integrity.
    
    Args:
        encrypted_key: Ciphertext bytes (without auth tag).
        iv: 12-byte Initialization Vector.
        auth_tag: 16-byte GCM authentication tag.
        master_key: Optional 32-byte key.
        
    Returns:
        Plaintext string of the decrypted API key.
        
    Raises:
        DecryptionError: If the tag is invalid (tampered) or decryption fails.
    """
    if not encrypted_key or not iv or not auth_tag:
        raise ValueError("encrypted_key, iv, and auth_tag are all required for decryption.")
    
    key = master_key or get_encryption_master_key()
    aesgcm = AESGCM(key)
    
    ciphertext_with_tag = encrypted_key + auth_tag
    
    try:
        decrypted_bytes = aesgcm.decrypt(iv, ciphertext_with_tag, None)
        return decrypted_bytes.decode('utf-8')
    except InvalidTag as e:
        raise DecryptionError("Decryption failed: data or authentication tag has been tampered with.") from e
    except Exception as e:
        raise DecryptionError(f"Decryption failed: {str(e)}") from e
