import hmac
import hashlib
import time
from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import User
from apps.authentication.services import check_telegram_hash, get_or_create_telegram_user


class TelegramAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.bot_token = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
        self.tg_data = {
            "id": 12345678,
            "first_name": "Sardor",
            "last_name": "Rahimov",
            "username": "sardor_dev",
            "auth_date": int(time.time()),
        }

    def _generate_valid_hash(self, data: dict, bot_token: str) -> str:
        check_dict = {k: v for k, v in data.items() if k != "hash"}
        data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(check_dict.items())])
        secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        return hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def test_valid_telegram_hash(self):
        """To'g'ri hisoblangan Telegram HMAC xesh muvaffaqiyatli tekshirilishi kerak."""
        data = self.tg_data.copy()
        data["hash"] = self._generate_valid_hash(data, self.bot_token)
        is_valid = check_telegram_hash(data, bot_token=self.bot_token)
        self.assertTrue(is_valid)

    def test_tampered_telegram_hash(self):
        """O'zgartirilgan (soxta) Telegram xesh rad etilishi kerak."""
        data = self.tg_data.copy()
        data["hash"] = "fake_invalid_hash_value_1234567890abcdef"
        is_valid = check_telegram_hash(data, bot_token=self.bot_token)
        self.assertFalse(is_valid)

    def test_expired_telegram_auth_date(self):
        """24 soatdan ortiq vaqt o'tgan Telegram ma'lumotlari rad etilishi kerak."""
        data = self.tg_data.copy()
        data["auth_date"] = int(time.time()) - 90000  # 25 soat oldin
        data["hash"] = self._generate_valid_hash(data, self.bot_token)
        is_valid = check_telegram_hash(data, bot_token=self.bot_token)
        self.assertFalse(is_valid)

    def test_get_or_create_telegram_user(self):
        """Telegram ma'lumotlaridan foydalanuvchi to'g'ri yaratilishi va o'qituvchi roli berilishi."""
        user, created = get_or_create_telegram_user(self.tg_data)
        self.assertTrue(created)
        self.assertEqual(user.telegram_id, 12345678)
        self.assertEqual(user.first_name, "Sardor")
        self.assertEqual(user.role, "teacher")

        # Qayta murojaat qilinganda yangi user yaratilmasligi kerak
        user2, created2 = get_or_create_telegram_user(self.tg_data)
        self.assertFalse(created2)
        self.assertEqual(user.id, user2.id)

    def test_telegram_callback_view_forbidden_on_bad_hash(self):
        """Callback endpointi soxta xesh yuborilganda 403 Forbidden qaytarishi shart."""
        url = reverse("auth:telegram_callback")
        bad_payload = {
            "id": 9999999,
            "first_name": "Hacker",
            "auth_date": int(time.time()),
            "hash": "invalid_hash_signature",
        }
        response = self.client.post(
            url,
            data=bad_payload,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
