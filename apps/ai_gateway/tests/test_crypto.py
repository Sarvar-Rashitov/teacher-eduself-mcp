import os
import pytest
from cryptography.exceptions import InvalidTag
from django.contrib.auth import get_user_model

from ai_gateway.crypto import AESGCMCipher, mask_api_key, get_default_master_key
from ai_gateway.models import UserApiKey

User = get_user_model()


class TestAESGCMCrypto:
    def test_round_trip_encryption_decryption(self):
        secret = "sk-proj-very-secret-openai-api-key-12345"
        master_key = os.urandom(32)

        ciphertext, iv, auth_tag = AESGCMCipher.encrypt(secret, master_key=master_key)

        assert len(iv) == 12
        assert len(auth_tag) == 16
        assert ciphertext != secret.encode()

        decrypted = AESGCMCipher.decrypt(ciphertext, iv, auth_tag, master_key=master_key)
        assert decrypted == secret

    def test_tampered_ciphertext_fails_integrity_check(self):
        secret = "super-secret-claude-key"
        master_key = os.urandom(32)

        ciphertext, iv, auth_tag = AESGCMCipher.encrypt(secret, master_key=master_key)

        # Tamper 1 byte of ciphertext
        tampered_ct = bytearray(ciphertext)
        tampered_ct[0] ^= 0xFF

        with pytest.raises(InvalidTag):
            AESGCMCipher.decrypt(bytes(tampered_ct), iv, auth_tag, master_key=master_key)

    def test_tampered_auth_tag_fails(self):
        secret = "my-secret-key"
        master_key = os.urandom(32)

        ciphertext, iv, auth_tag = AESGCMCipher.encrypt(secret, master_key=master_key)

        # Tamper auth tag
        tampered_tag = bytearray(auth_tag)
        tampered_tag[0] ^= 0x01

        with pytest.raises(InvalidTag):
            AESGCMCipher.decrypt(ciphertext, iv, bytes(tampered_tag), master_key=master_key)

    def test_wrong_master_key_fails(self):
        secret = "my-secret-key"
        key_1 = os.urandom(32)
        key_2 = os.urandom(32)

        ciphertext, iv, auth_tag = AESGCMCipher.encrypt(secret, master_key=key_1)

        with pytest.raises(InvalidTag):
            AESGCMCipher.decrypt(ciphertext, iv, auth_tag, master_key=key_2)

    def test_invalid_key_length_raises_value_error(self):
        with pytest.raises(ValueError):
            AESGCMCipher.encrypt("text", master_key=b"too-short")

    def test_mask_api_key(self):
        assert mask_api_key("sk-proj-abcdef1234567890xyz") == "sk-proj-...0xyz"
        assert mask_api_key("AIzaSyD1234567890abcdef") == "AIza...cdef"
        assert mask_api_key("short") == "****"
        assert mask_api_key("") == ""

    @pytest.mark.django_db
    def test_user_api_key_model_storage(self):
        """
        Self-Audit Checklist Item:
        API kalitlari bazada ochiq matn (plain text) holatida saqlanmayaptimi?
        """
        user = User.objects.create_user(username="teacher_key_test", password="PassWord123!")
        plain_key = "sk-proj-live-openai-key-secret-999"

        api_key_obj = UserApiKey.objects.create(
            user=user,
            provider="openai",
        )
        api_key_obj.set_key(plain_key)
        api_key_obj.save()

        # Reload from DB
        reloaded = UserApiKey.objects.get(id=api_key_obj.id)

        # Plaintext is NOT anywhere in raw DB columns
        assert plain_key.encode() not in bytes(reloaded.encrypted_key)
        assert plain_key not in reloaded.masked_key
        assert plain_key not in str(reloaded)

        # Decryption returns the exact plaintext key
        assert reloaded.get_key() == plain_key
        assert reloaded.masked_key == "sk-proj-...-999"
