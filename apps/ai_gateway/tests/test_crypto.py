"""
Unit testlar: AES-256-GCM BYOK Shifrlash va Ochish.
Spetsifikatsiya: .docs/ai/BYOK.md
"""
import os
import pytest
from apps.ai_gateway.crypto import (
    encrypt_api_key,
    decrypt_api_key,
    mask_api_key,
    get_master_key,
    DecryptionError
)


class TestBYOKCrypto:
    def test_encrypt_and_decrypt_roundtrip(self):
        """Kalit to'g'ri shifrlanishi va asl holatida ochilishi kerak."""
        original_key = "sk-proj-EduSelfTeacherSecretKey998877"
        enc_data, iv, tag, masked = encrypt_api_key(original_key)

        assert len(iv) == 12, "IV uzunligi 12 bayt bo'lishi shart"
        assert len(tag) == 16, "GCM auth_tag 16 bayt bo'lishi shart"
        assert enc_data != original_key.encode('utf-8')
        assert "EduSelfTeacher" not in masked

        # Dekriptlash
        decrypted = decrypt_api_key(enc_data, iv, tag)
        assert decrypted == original_key

    def test_mask_api_key_formats(self):
        """Frontend uchun kalitni xavfsiz niqoblash."""
        assert mask_api_key("sk-proj-1234567890abcdef") == "sk-proj-...cdef"
        assert mask_api_key("sk-ant-api03-abcdef1234") == "sk-...1234"
        assert mask_api_key("AIzaSyD1234567890abcdef") == "AIza...cdef"
        assert mask_api_key("short") == "...rt"
        assert mask_api_key("") == ""

    def test_tampered_ciphertext_raises_decryption_error(self):
        """Shifrlangan matn o'zgartirilsa (tampered), DecryptionError qo'zg'atilishi shart."""
        original_key = "sk-test-integrity-check"
        enc_data, iv, tag, _ = encrypt_api_key(original_key)

        # 1 baytini buzamiz
        corrupted_data = bytearray(enc_data)
        corrupted_data[0] ^= 0xFF

        with pytest.raises(DecryptionError, match="yaxlitligi buzilgan"):
            decrypt_api_key(bytes(corrupted_data), iv, tag)

    def test_tampered_auth_tag_raises_decryption_error(self):
        """Autentifikatsiya tegi buzilsa, DecryptionError qo'zg'atilishi shart."""
        original_key = "sk-test-tag-check"
        enc_data, iv, tag, _ = encrypt_api_key(original_key)

        corrupted_tag = bytearray(tag)
        corrupted_tag[-1] ^= 0x01

        with pytest.raises(DecryptionError):
            decrypt_api_key(enc_data, iv, bytes(corrupted_tag))

    def test_wrong_master_key_fails(self):
        """Boshqa master key bilan ochmoqchi bo'linganda rad etilishi kerak."""
        key_1 = os.urandom(32)
        key_2 = os.urandom(32)

        enc_data, iv, tag, _ = encrypt_api_key("sk-test-secret", master_key=key_1)

        with pytest.raises(DecryptionError):
            decrypt_api_key(enc_data, iv, tag, master_key=key_2)

    def test_empty_key_raises_value_error(self):
        """Bo'sh kalit yuborilsa ValueError bo'lishi kerak."""
        with pytest.raises(ValueError, match="bo'sh bo'lishi mumkin emas"):
            encrypt_api_key("")
