from typing import Any, Dict, List, Type, Union
from .base import BaseQuestionType
from .exceptions import QuestionTypeNotFoundError, QuestionValidationError


class QuestionTypeRegistry:
    """
    Savol turlari reestri (Registry Pattern).
    Yadro kodiga tegmasdan yangi savol turlarini qo'shish imkonini beradi.
    """

    def __init__(self):
        self._registry: Dict[str, BaseQuestionType] = {}

    def register(self, item: Union[Type[BaseQuestionType], BaseQuestionType]) -> None:
        """
        Yangi savol turini ro'yxatga oladi.
        Sinf yoki obyekt instansiyasini qabul qiladi.
        """
        instance = item() if isinstance(item, type) else item
        if not instance.type_id:
            raise QuestionValidationError(f"{instance.__class__.__name__} uchun 'type_id' ko'rsatilmagan.")

        self._registry[instance.type_id] = instance

    def get(self, type_id: str) -> BaseQuestionType:
        """
        Berilgan type_id bo'yicha savol turi handlerini qaytaradi.
        Topilmasa QuestionTypeNotFoundError chiqaradi.
        """
        if type_id not in self._registry:
            raise QuestionTypeNotFoundError(
                f"Savol turi '{type_id}' tizimda ro'yxatga olinmagan. "
                f"Mavjud turlar: {list(self._registry.keys())}"
            )
        return self._registry[type_id]

    def is_registered(self, type_id: str) -> bool:
        """Savol turi mavjudligini tekshirish."""
        return type_id in self._registry

    def list_all(self) -> List[Dict[str, Any]]:
        """Barcha ro'yxatdan o'tgan savol turlari ro'yxatini qaytarish."""
        return [
            {
                "type_id": handler.type_id,
                "name": handler.name,
                "category": handler.category,
                "auto_graded": handler.auto_graded,
            }
            for handler in self._registry.values()
        ]


# Yagona global instansiya
registry = QuestionTypeRegistry()
