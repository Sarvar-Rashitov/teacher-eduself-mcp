import pytest
from cryptography.exceptions import InvalidTag
from apps.ai_gateway.crypto import (
    encrypt_api_key,
    decrypt_api_key,
    mask_key,
    get_master_key,
)
from apps.ai_gateway.models import UserApiKey
from apps.authentication.models import User


class TestCryptoUtilities:
    def test_encrypt_decrypt_roundtrip(self):
        plain_key = "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"
        ciphertext, iv, auth_tag, masked = encrypt_api_key(plain_key)

        assert isinstance(ciphertext, bytes)
        assert isinstance(iv, bytes)
        assert len(iv) == 12  # GCM 96-bit nonce
        assert isinstance(auth_tag, bytes)
        assert len(auth_tag) == 16  # 128-bit GCM tag
        assert plain_key not in str(ciphertext)

        # Decrypt
        decrypted = decrypt_api_key(ciphertext, iv, auth_tag)
        assert decrypted == plain_key

    def test_tamper_detection(self):
        plain_key = "sk-test-super-secret-key"
        ciphertext, iv, auth_tag, _ = encrypt_api_key(plain_key)

        # Corrupt ciphertext byte
        corrupted_ciphertext = bytearray(ciphertext)
        corrupted_ciphertext[0] ^= 0xFF

        with pytest.raises(InvalidTag):
            decrypt_api_key(bytes(corrupted_ciphertext), iv, auth_tag)

        # Corrupt auth tag byte
        corrupted_tag = bytearray(auth_tag)
        corrupted_tag[0] ^= 0xFF

        with pytest.raises(InvalidTag):
            decrypt_api_key(ciphertext, iv, bytes(corrupted_tag))

    def test_mask_key_formatting(self):
        assert mask_key("sk-proj-abcdef1234567890") == "sk-...7890"
        assert mask_key("AIzaSyD1234567890abcdef") == "AIza...cdef"
        assert mask_key("short") == "****"

    @pytest.mark.django_db
    def test_user_api_key_model(self):
        user = User.objects.create_user(
            username="crypto_teacher",
            email="crypto_teacher@example.com",
            password="TestPassword123!",
            first_name="Crypto",
            last_name="Teacher",
        )

        key_obj = UserApiKey(user=user, provider="openai")
        raw_key = "sk-proj-my-openai-key-9999"
        key_obj.set_key(raw_key)
        key_obj.save()

        # Reload from DB
        loaded = UserApiKey.objects.get(id=key_obj.id)
        assert loaded.masked_key == "sk-...9999"
        assert loaded.get_key() == raw_key
        assert loaded.encrypted_key != raw_key.encode("utf-8")
