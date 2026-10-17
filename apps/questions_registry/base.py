# apps/questions_registry/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .exceptions import QuestionValidationError


@dataclass
class EvaluationResult:
    """
    Savolga berilgan javobni baholash natijasi.
    """
    is_correct: bool
    score: int
    score_ratio: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class BaseQuestionType(ABC):
    """
    29 xil savol formati uchun asosiy abstrakt sinf.
    QUESTION_TYPES.md §1 talablari asosida.
    """
    type_id: str = ""
    name: str = ""
    category: str = "assessment"  # 'assessment', 'formative', 'presentation'
    description: str = ""

    @abstractmethod
    def validate_payload(self, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None) -> bool:
        """
        O'qituvchi tomonidan kiritilgan options va correct_answer strukturasini tekshirish.
        Noto'g'ri bo'lsa QuestionValidationError chiqaradi.
        """
        pass

    @abstractmethod
    def sanitize_for_student(self, options: Any) -> Any:
        """
        Zero-Knowledge Question Delivery:
        Talaba qurilmasiga uzatishdan oldin to'g'ri javoblar va maxfiy kalitlarni tozalash.
        """
        pass

    @abstractmethod
    def evaluate_answer(
        self,
        submitted_answer: Any,
        correct_answer: Any,
        max_points: int = 1000,
        accepted_alternatives: Optional[List] = None
    ) -> EvaluationResult:
        """
        Talaba javobini tekshirib ball hisoblash.
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Tizim yoki UI uchun metama'lumotlarni qaytarish."""
        return {
            'type_id': self.type_id,
            'name': self.name,
            'category': self.category,
            'description': self.description,
        }
