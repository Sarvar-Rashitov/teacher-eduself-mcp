"""
Unit testlar: UserApiKey va TokenUsageLog modellari.
Spetsifikatsiya: .docs/ai/BYOK.md & AI_COSTS.md
"""
import pytest
from decimal import Decimal
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from apps.ai_gateway.models import UserApiKey, TokenUsageLog, AIProviderChoice

User = get_user_model()


@pytest.mark.django_db
class TestUserApiKeyModel:
    @pytest.fixture
    def teacher(self):
        return User.objects.create_user(
            username='ai_teacher',
            password='password123',
            role='teacher'
        )

    def test_create_and_retrieve_user_api_key(self, teacher):
        """Foydalanuvchi kalitini shifrlab saqlash va ochib olish."""
        plain_key = "sk-proj-super-secret-openai-api-key-12345"
        key_obj = UserApiKey.objects.create(
            user=teacher,
            provider=AIProviderChoice.OPENAI
        )
        key_obj.set_key(plain_key)
        key_obj.save()

        # Qayta o'qish
        saved_obj = UserApiKey.objects.get(id=key_obj.id)
        assert saved_obj.masked_key == "sk-proj-...2345"
        assert bytes(saved_obj.encrypted_key) != plain_key.encode('utf-8')
        assert saved_obj.get_key() == plain_key

    def test_unique_user_provider_constraint(self, teacher):
        """Bitta foydalanuvchi bitta provayder uchun faqat 1 ta kalit saqlay oladi."""
        k1 = UserApiKey.objects.create(user=teacher, provider=AIProviderChoice.OPENAI)
        k1.set_key("sk-key-1")
        k1.save()

        with pytest.raises(IntegrityError):
            k2 = UserApiKey.objects.create(user=teacher, provider=AIProviderChoice.OPENAI)
            k2.set_key("sk-key-2")
            k2.save()


@pytest.mark.django_db
class TestTokenUsageLogModel:
    def test_create_usage_log(self):
        """Token sarfi logini to'g'ri yaratish."""
        log = TokenUsageLog.objects.create(
            provider='openai',
            model_name='gpt-4o-mini',
            prompt_tokens=1500,
            completion_tokens=500,
            total_tokens=2000,
            estimated_cost_usd=Decimal('0.000525'),
            latency_ms=850,
            task_type='quiz_generation'
        )
        assert log.total_tokens == 2000
        assert log.estimated_cost_usd == Decimal('0.000525')
        assert "openai/gpt-4o-mini" in str(log)
