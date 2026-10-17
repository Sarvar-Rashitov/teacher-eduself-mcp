# apps/questions_registry/registry.py
import logging
from typing import Dict, List, Type, Union
from .base import BaseQuestionType
from .exceptions import InvalidQuestionTypeError

logger = logging.getLogger(__name__)


class QuestionTypeRegistry:
    """
    Savol turlari markaziy reestri (Registry Pattern).
    QUESTION_TYPES.md §1 asosida.
    """
    def __init__(self):
        self._registry: Dict[str, BaseQuestionType] = {}

    def register(self, item: Union[BaseQuestionType, Type[BaseQuestionType]]) -> None:
        """
        Yangi savol turini ro'yxatga olish.
        Klass yoki obyekt instansiyasi qabul qilinadi.
        """
        instance = item() if isinstance(item, type) else item
        if not isinstance(instance, BaseQuestionType):
            raise TypeError(f"{item} BaseQuestionType dan meros olishi shart.")

        if not instance.type_id:
            raise ValueError(f"{item} da 'type_id' belgilanmagan.")

        self._registry[instance.type_id] = instance
        logger.debug(f"Savol turi ro'yxatga olindi: {instance.type_id} ({instance.name})")

    def get(self, type_id: str) -> BaseQuestionType:
        """
        type_id bo'yicha savol turi handlerini olish.
        """
        handler = self._registry.get(type_id)
        if not handler:
            raise InvalidQuestionTypeError(f"'{type_id}' nomli savol turi ro'yxatda topilmadi.")
        return handler

    def is_valid_type(self, type_id: str) -> bool:
        return type_id in self._registry

    def list_types(self) -> List[Dict]:
        """Barcha mavjud savol turlari ro'yxatini qaytarish."""
        return [handler.get_metadata() for handler in self._registry.values()]

    def clear(self):
        """Testlar uchun tozalash."""
        self._registry.clear()


# Global Singleton nusxa
question_registry = QuestionTypeRegistry()
