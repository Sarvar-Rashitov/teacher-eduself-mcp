import pytest
from django.contrib.auth import get_user_model
from apps.ai_gateway.crypto import (
    encrypt_api_key,
    decrypt_api_key,
    mask_api_key,
    get_encryption_master_key,
    DecryptionError,
)
from apps.ai_gateway.models import UserApiKey, AIProviderChoices

User = get_user_model()


@pytest.mark.django_db
def test_aes_256_gcm_roundtrip():
    original_key = "sk-proj-test1234567890abcdefghijklmnopqrstuvwxyz"
    encrypted, iv, tag = encrypt_api_key(original_key)

    assert encrypted != original_key.encode()
    assert len(iv) == 12
    assert len(tag) == 16

    decrypted = decrypt_api_key(encrypted, iv, tag)
    assert decrypted == original_key


def test_unique_iv_per_encryption():
    key = "sk-ant-api03-test-token"
    enc1, iv1, tag1 = encrypt_api_key(key)
    enc2, iv2, tag2 = encrypt_api_key(key)

    assert iv1 != iv2
    assert enc1 != enc2
    assert tag1 != tag2


def test_tampered_ciphertext_fails_auth_tag():
    key = "AIzaSyB1234567890abcdef"
    encrypted, iv, tag = encrypt_api_key(key)

    # Tamper with the 1st byte of ciphertext
    tampered_bytes = bytearray(encrypted)
    tampered_bytes[0] ^= 0xFF
    tampered = bytes(tampered_bytes)

    with pytest.raises(DecryptionError):
        decrypt_api_key(tampered, iv, tag)


def test_tampered_auth_tag_fails_decryption():
    key = "AIzaSyB1234567890abcdef"
    encrypted, iv, tag = encrypt_api_key(key)

    # Tamper with the tag
    tampered_tag = bytearray(tag)
    tampered_tag[0] ^= 0xFF

    with pytest.raises(DecryptionError):
        decrypt_api_key(encrypted, iv, bytes(tampered_tag))


def test_mask_api_key_formatting():
    assert mask_api_key("sk-proj-1234567890abcdef") == "sk-proj-...cdef"
    assert mask_api_key("sk-ant-1234567890abcdef") == "sk-ant-...cdef"
    assert mask_api_key("AIzaSyB1234567890xyz") == "AIza...0xyz"
    assert mask_api_key("short12") == "sh...12"
    assert mask_api_key("") == ""


@pytest.mark.django_db
def test_user_api_key_model_lifecycle():
    user = User.objects.create_user(username="teacher_byok", password="SecurePassword123!")
    key_record = UserApiKey(user=user, provider=AIProviderChoices.OPENAI)
    raw_key = "sk-proj-my-super-secret-openai-api-key"

    key_record.set_key(raw_key)
    key_record.save()

    # Verify database fields do not store plaintext
    refetched = UserApiKey.objects.get(id=key_record.id)
    assert bytes(refetched.encrypted_key) != raw_key.encode()
    assert refetched.masked_key.startswith("sk-proj-...")
    assert refetched.is_valid is True

    # Verify round-trip retrieval
    assert refetched.get_key() == raw_key

    # Verify mark_used updates timestamp
    assert refetched.last_used_at is None
    refetched.mark_used()
    refetched.refresh_from_db()
    assert refetched.last_used_at is not None
