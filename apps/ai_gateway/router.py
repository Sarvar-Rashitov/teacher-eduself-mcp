"""
Model Routing Engine & Circuit Breaker.
Spetsifikatsiya: .docs/ai/MODEL_ROUTING.md
"""
import time
import logging
from typing import Dict, Any, List, Optional, Tuple, Type, TypeVar
from pydantic import BaseModel
from django.conf import settings

from apps.ai_gateway.base import (
    BaseAIAdapter,
    ModelConfig,
    TextResponse,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
    AIProviderError
)
from apps.ai_gateway.adapters.openai_adapter import OpenAIAdapter
from apps.ai_gateway.adapters.gemini_adapter import GeminiAdapter
from apps.ai_gateway.adapters.claude_adapter import ClaudeAdapter
from apps.ai_gateway.adapters.groq_adapter import GroqAdapter
from apps.ai_gateway.adapters.deepseek_adapter import DeepSeekAdapter
from apps.ai_gateway.models import UserApiKey, TokenUsageLog

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class CircuitBreaker:
    """
    Provayderlar ishdan chiqqanda kaskadli himoya (Circuit Breaker).
    MODEL_ROUTING.md 4-bo'lim.
    """
    FAILURE_THRESHOLD = 3
    COOLDOWN_SECONDS = 60.0

    def __init__(self):
        self._failures: Dict[str, int] = {}
        self._states: Dict[str, str] = {}  # 'CLOSED', 'OPEN', 'HALF_OPEN'
        self._tripped_at: Dict[str, float] = {}

    def is_available(self, provider: str) -> bool:
        state = self._states.get(provider, 'CLOSED')
        if state == 'CLOSED':
            return True

        if state == 'OPEN':
            tripped_time = self._tripped_at.get(provider, 0.0)
            if time.time() - tripped_time > self.COOLDOWN_SECONDS:
                # Cooldown tugadi -> Sinov so'rovi uchun HALF_OPEN
                self._states[provider] = 'HALF_OPEN'
                return True
            return False

        if state == 'HALF_OPEN':
            return True

        return True

    def record_success(self, provider: str):
        self._failures[provider] = 0
        self._states[provider] = 'CLOSED'

    def record_failure(self, provider: str):
        fails = self._failures.get(provider, 0) + 1
        self._failures[provider] = fails
        if fails >= self.FAILURE_THRESHOLD:
            self._states[provider] = 'OPEN'
            self._tripped_at[provider] = time.time()
            logger.warning(f"Circuit Breaker TRIP: {provider} ketma-ket {fails} marta xato berdi. 60s OPEN.")

    def reset(self, provider: Optional[str] = None):
        if provider:
            self._failures[provider] = 0
            self._states[provider] = 'CLOSED'
        else:
            self._failures.clear()
            self._states.clear()
            self._tripped_at.clear()


class ModelRouter:
    """
    Vazifa murakkabligi, narx va tezlik bo'yicha model tanlovchi dvigatel.
    """
    ROUTING_MATRIX: Dict[str, List[Tuple[str, str]]] = {
        # Katta kitob / darslik (>100K token kontekst)
        'large_document': [
            ('gemini', 'gemini-1.5-pro'),
            ('claude', 'claude-3-5-sonnet-20241022'),
            ('openai', 'gpt-4o'),
        ],
        # Matematika va STEM
        'stem_math': [
            ('claude', 'claude-3-5-sonnet-20241022'),
            ('deepseek', 'deepseek-reasoner'),
            ('openai', 'gpt-4o'),
        ],
        # Dasturlash va IT
        'coding_it': [
            ('claude', 'claude-3-5-sonnet-20241022'),
            ('deepseek', 'deepseek-chat'),
            ('openai', 'gpt-4o'),
        ],
        # Jonli darsda tezkor viktorina (<1s)
        'quick_quiz': [
            ('groq', 'llama-3.3-70b-versatile'),
            ('openai', 'gpt-4o-mini'),
            ('deepseek', 'deepseek-chat'),
        ],
        # Standart dars viktorinasi (tejamkor va barqaror)
        'standard': [
            ('openai', 'gpt-4o-mini'),
            ('deepseek', 'deepseek-chat'),
            ('groq', 'llama-3.3-70b-versatile'),
        ],
    }

    def __init__(self):
        self.adapters: Dict[str, BaseAIAdapter] = {
            'openai': OpenAIAdapter(),
            'gemini': GeminiAdapter(),
            'claude': ClaudeAdapter(),
            'groq': GroqAdapter(),
            'deepseek': DeepSeekAdapter(),
        }
        self.circuit_breaker = CircuitBreaker()

    def get_adapter(self, provider: str) -> BaseAIAdapter:
        if provider not in self.adapters:
            raise KeyError(f"Provayder adapteri topilmadi: {provider}")
        return self.adapters[provider]

    def select_targets(
        self,
        task_type: str = 'standard',
        user: Optional[Any] = None,
        estimated_tokens: int = 0,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """
        3 Pog'onali tanlov ierarxiyasi (MODEL_ROUTING.md 3-bo'lim):
        1-pog'ona: User Override / BYOK
        2-pog'ona: Kontekst hajmi (>100K token bo'lsa -> Gemini)
        3-pog'ona: Vazifalar matritsasi
        """
        # 1-Pog'ona: Foydalanuvchi aniq ko'rsatgan bo'lsa
        if preferred_provider:
            model = preferred_model or ""
            return [(preferred_provider, model)]

        # Agar foydalanuvchida shaxsiy BYOK kaliti bo'lsa
        if user and user.is_authenticated:
            byok = UserApiKey.objects.filter(user=user, is_valid=True).first()
            if byok:
                return [(byok.provider, preferred_model or "")]

        # 2-Pog'ona: Katta kontekst oynasi talab qilinsa
        if estimated_tokens > 100000:
            return self.ROUTING_MATRIX['large_document']

        # 3-Pog'ona: Vazifa bo'yicha standart matritsa
        return self.ROUTING_MATRIX.get(task_type, self.ROUTING_MATRIX['standard'])

    async def execute_text(
        self,
        messages: List[Dict[str, str]],
        task_type: str = 'standard',
        user: Optional[Any] = None,
        config: Optional[ModelConfig] = None,
        estimated_tokens: int = 0
    ) -> TextResponse:
        """
        Matnli generatsiyani kaskadli zaxira (Fallback Cascade) bilan bajarish.
        """
        targets = self.select_targets(
            task_type=task_type,
            user=user,
            estimated_tokens=estimated_tokens,
            preferred_provider=getattr(config, 'preferred_provider', None),
            preferred_model=config.model_name if config else None
        )

        last_error = None
        cfg = config or ModelConfig()

        for provider, model_name in targets:
            if not self.circuit_breaker.is_available(provider):
                logger.info(f"Circuit Breaker: {provider} o'chirilgan, keyingi zaxiraga o'tilmoqda.")
                continue

            adapter = self.get_adapter(provider)
            target_config = ModelConfig(
                model_name=model_name or cfg.model_name,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                top_p=cfg.top_p,
                timeout_seconds=cfg.timeout_seconds,
                api_key_override=self._resolve_api_key(provider, user, cfg)
            )

            try:
                response = await adapter.generate_text(messages, target_config)
                self.circuit_breaker.record_success(provider)
                self._log_usage(user, provider, target_config.model_name, response.usage, response.latency_ms, task_type, adapter)
                return response
            except (AIProviderRateLimitError, AIProviderServerError, AIProviderTimeoutError) as e:
                logger.warning(f"{provider} xatosi: {e}. Zaxiraga o'tilmoqda...")
                self.circuit_breaker.record_failure(provider)
                last_error = e
                continue
            except Exception as e:
                # Boshqa xatolar (masalan, ContentFilter yoki Auth) to'g'ridan-to'g'ri qaytariladi
                logger.error(f"{provider} da jiddiy xato: {e}")
                raise

        if last_error:
            raise last_error
        raise AIProviderError("Hech qaysi AI provayderi mavjud emas.")

    async def execute_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Type[T],
        task_type: str = 'standard',
        user: Optional[Any] = None,
        config: Optional[ModelConfig] = None,
        estimated_tokens: int = 0
    ) -> T:
        """
        Strukturali JSON generatsiyasini kaskadli zaxira bilan bajarish.
        """
        targets = self.select_targets(
            task_type=task_type,
            user=user,
            estimated_tokens=estimated_tokens,
            preferred_provider=getattr(config, 'preferred_provider', None),
            preferred_model=config.model_name if config else None
        )

        last_error = None
        cfg = config or ModelConfig()

        for provider, model_name in targets:
            if not self.circuit_breaker.is_available(provider):
                logger.info(f"Circuit Breaker: {provider} o'chirilgan, keyingi zaxiraga o'tilmoqda.")
                continue

            adapter = self.get_adapter(provider)
            target_config = ModelConfig(
                model_name=model_name or cfg.model_name,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                top_p=cfg.top_p,
                timeout_seconds=cfg.timeout_seconds,
                api_key_override=self._resolve_api_key(provider, user, cfg)
            )

            try:
                result = await adapter.generate_structured(messages, schema, target_config)
                self.circuit_breaker.record_success(provider)
                return result
            except (AIProviderRateLimitError, AIProviderServerError, AIProviderTimeoutError) as e:
                logger.warning(f"{provider} strukturali generatsiya xatosi: {e}. Zaxiraga o'tilmoqda...")
                self.circuit_breaker.record_failure(provider)
                last_error = e
                continue
            except Exception as e:
                logger.error(f"{provider} da xato: {e}")
                raise

        if last_error:
            raise last_error
        raise AIProviderError("Hech qaysi AI provayderi mavjud emas.")

    def _resolve_api_key(self, provider: str, user: Optional[Any], config: ModelConfig) -> Optional[str]:
        if config.api_key_override:
            return config.api_key_override
        if user and user.is_authenticated:
            key_record = UserApiKey.objects.filter(user=user, provider=provider, is_valid=True).first()
            if key_record:
                try:
                    return key_record.get_key()
                except Exception as e:
                    logger.error(f"Foydalanuvchi API kalitini dekriptlashda xato: {e}")
        return None

    def _log_usage(
        self,
        user: Optional[Any],
        provider: str,
        model_name: str,
        usage: Any,
        latency_ms: int,
        task_type: str,
        adapter: BaseAIAdapter
    ):
        try:
            cost = adapter.estimate_cost(usage, model_name)
            u = user if (user and getattr(user, 'is_authenticated', False)) else None
            TokenUsageLog.objects.create(
                user=u,
                provider=provider,
                model_name=model_name,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cached_tokens=usage.cached_tokens,
                estimated_cost_usd=cost,
                latency_ms=latency_ms,
                task_type=task_type
            )
        except Exception as e:
            logger.warning(f"Token sarfini qayd etishda xato: {e}")


# Singleton ModelRouter
model_router = ModelRouter()
