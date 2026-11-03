"""
Unit and integration tests for Telegram Login Widget HMAC-SHA256 authentication.
"""

import hmac
import hashlib
import time
import json
import pytest
from django.test import Client
from apps.authentication.services import check_telegram_hash, authenticate_telegram_user
from apps.authentication.models import User


def generate_valid_telegram_payload(data: dict, bot_token: str) -> dict:
    """Helper to generate a cryptographically valid Telegram Widget payload."""
    payload = data.copy()
    check_pairs = [f"{k}={v}" for k, v in sorted(payload.items()) if k != 'hash']
    data_check_string = "\n".join(check_pairs)

    secret_key = hashlib.sha256(bot_token.encode('utf-8')).digest()
    valid_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    payload['hash'] = valid_hash
    return payload


def test_telegram_hash_validation_success():
    """Verify that a valid HMAC hash is accepted."""
    bot_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
    valid_data = {
        'id': '100200300',
        'first_name': 'Malika',
        'username': 'malika_teacher',
        'auth_date': str(int(time.time()))
    }
    signed_payload = generate_valid_telegram_payload(valid_data, bot_token)

    assert check_telegram_hash(signed_payload, bot_token=bot_token) is True


def test_telegram_hash_validation_rejects_expired():
    """Verify that auth_date older than 24 hours is rejected."""
    bot_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
    expired_data = {
        'id': '100200300',
        'first_name': 'Malika',
        'auth_date': str(int(time.time()) - 90000)  # > 24 hours
    }
    signed_payload = generate_valid_telegram_payload(expired_data, bot_token)

    assert check_telegram_hash(signed_payload, bot_token=bot_token) is False


def test_telegram_hash_validation_rejects_tampered_payload():
    """Verify that tampered data with valid-looking hash is rejected."""
    bot_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
    valid_data = {
        'id': '100200300',
        'first_name': 'Malika',
        'auth_date': str(int(time.time()))
    }
    signed_payload = generate_valid_telegram_payload(valid_data, bot_token)

    # Tamper with first_name
    signed_payload['first_name'] = 'Hacker'

    assert check_telegram_hash(signed_payload, bot_token=bot_token) is False


def test_telegram_hash_validation_rejects_missing_hash():
    """Verify that payload without hash is rejected."""
    bot_token = "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
    assert check_telegram_hash({'id': '123'}, bot_token=bot_token) is False


@pytest.mark.django_db
def test_authenticate_telegram_user_creates_teacher_and_profile():
    """Verify service creates a new teacher with linked TeacherProfile."""
    data = {
        'id': '99887766',
        'first_name': 'Botir',
        'last_name': 'Aliyev',
        'username': 'botir_math',
        'photo_url': 'https://t.me/i/userpic/320/botir.jpg',
    }
    user, created = authenticate_telegram_user(data)

    assert created is True
    assert user.telegram_id == 99887766
    assert user.username == 'botir_math'
    assert user.first_name == 'Botir'
    assert user.role == 'teacher'
    assert hasattr(user, 'teacher_profile') is True


@pytest.mark.django_db
def test_telegram_auth_callback_endpoint_success(settings):
    """Test full HTTP POST flow to /auth/telegram/ callback."""
    settings.TELEGRAM_BOT_TOKEN = "test_bot_token_secret_123"
    client = Client()

    raw_data = {
        'id': '55443322',
        'first_name': 'Dilnoza',
        'username': 'dilnoza_teacher',
        'auth_date': str(int(time.time())),
    }
    payload = generate_valid_telegram_payload(raw_data, settings.TELEGRAM_BOT_TOKEN)

    response = client.post(
        '/auth/telegram/',
        data=json.dumps(payload),
        content_type='application/json'
    )

    assert response.status_code == 200
    res_data = response.json()
    assert res_data['status'] == 'ok'
    assert res_data['user']['username'] == 'dilnoza_teacher'
    assert res_data['user']['role'] == 'teacher'

    # Verify user exists in database
    user = User.objects.get(telegram_id=55443322)
    assert user.first_name == 'Dilnoza'


@pytest.mark.django_db
def test_telegram_auth_callback_endpoint_rejects_forged(settings):
    """Test forged hash receives 403 Forbidden on /auth/telegram/."""
    settings.TELEGRAM_BOT_TOKEN = "test_bot_token_secret_123"
    client = Client()

    payload = {
        'id': '111111',
        'first_name': 'Attacker',
        'auth_date': str(int(time.time())),
        'hash': 'invalid_forged_hash_value'
    }

    response = client.post(
        '/auth/telegram/',
        data=json.dumps(payload),
        content_type='application/json'
    )

    assert response.status_code == 403
    assert 'Soxta yoki muddati o‘tgan' in response.json()['error']
