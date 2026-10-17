import hashlib
import hmac
import time
import pytest
from apps.authentication.models import User
from apps.authentication.services import (
    check_telegram_hash,
    authenticate_or_create_telegram_user
)

TEST_BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"


def generate_valid_telegram_payload(data: dict, bot_token: str) -> dict:
    """Yordamchi funksiya: haqiqiy Telegram heshini generatsiya qilish."""
    payload = data.copy()
    data_check_arr = [f"{k}={v}" for k, v in sorted(payload.items()) if k != 'hash']
    data_check_string = "\n".join(data_check_arr)
    secret_key = hashlib.sha256(bot_token.encode('utf-8')).digest()
    payload['hash'] = hmac.new(secret_key, data_check_string.encode('utf-8'), hashlib.sha256).hexdigest()
    return payload


class TestTelegramHashVerification:
    def test_valid_telegram_hash(self):
        """Haqiqiy Telegram heshi to'g'ri tekshirilishi."""
        raw_data = {
            'id': 987654321,
            'first_name': 'Ali',
            'username': 'ali_teacher',
            'auth_date': int(time.time()),
        }
        valid_payload = generate_valid_telegram_payload(raw_data, TEST_BOT_TOKEN)
        assert check_telegram_hash(valid_payload, bot_token=TEST_BOT_TOKEN) is True

    def test_tampered_telegram_hash(self):
        """Soxtalashtirilgan (o'zgartirilgan) ma'lumotlar rad etilishi."""
        raw_data = {
            'id': 987654321,
            'first_name': 'Ali',
            'username': 'ali_teacher',
            'auth_date': int(time.time()),
        }
        valid_payload = generate_valid_telegram_payload(raw_data, TEST_BOT_TOKEN)
        # Ma'lumotni o'zgartiramiz
        valid_payload['first_name'] = 'Vali'
        assert check_telegram_hash(valid_payload, bot_token=TEST_BOT_TOKEN) is False

    def test_expired_telegram_hash(self):
        """24 soatdan oshgan eski ma'lumotlar rad etilishi (SECURITY.md talabi)."""
        raw_data = {
            'id': 987654321,
            'first_name': 'Ali',
            'username': 'ali_teacher',
            'auth_date': int(time.time()) - 90000,  # 25 soat oldin
        }
        expired_payload = generate_valid_telegram_payload(raw_data, TEST_BOT_TOKEN)
        assert check_telegram_hash(expired_payload, bot_token=TEST_BOT_TOKEN) is False

    def test_missing_hash(self):
        """Hesh maydoni bo'lmaganda False qaytishi."""
        assert check_telegram_hash({'id': 123}, bot_token=TEST_BOT_TOKEN) is False


@pytest.mark.django_db
class TestTelegramUserCreation:
    def test_creates_new_user_and_profile(self):
        """Yangi Telegram foydalanuvchisi va uning TeacherProfile'i yaratilishi."""
        data = {
            'id': 555666777,
            'first_name': 'Nodira',
            'last_name': 'Karimova',
            'username': 'nodira_k',
            'photo_url': 'https://t.me/i/userpic/nodira.jpg'
        }
        user, created = authenticate_or_create_telegram_user(data)
        assert created is True
        assert user.telegram_id == 555666777
        assert user.first_name == 'Nodira'
        assert user.role == 'teacher'
        assert user.avatar_url == 'https://t.me/i/userpic/nodira.jpg'
        assert hasattr(user, 'teacher_profile')

    def test_returns_existing_user(self):
        """Mavjud Telegram foydalanuvchi qayta kirganda takroriy yaratilmasligi."""
        data = {
            'id': 777888999,
            'first_name': 'Jamshid',
            'username': 'jamshid_t',
        }
        user1, created1 = authenticate_or_create_telegram_user(data)
        assert created1 is True

        user2, created2 = authenticate_or_create_telegram_user(data)
        assert created2 is False
        assert user1.id == user2.id
