from abc import ABC, abstractmethod
from typing import Any, Dict, List
from .exceptions import QuestionValidationError


class BaseQuestionType(ABC):
    """
    Barcha 29 xil savol turlari uchun abstrakt tayanch sinf (Base Class).
    Har bir savol turi ushbu interfeysni to'liq bajarishi shart.
    """

    type_id: str = ""
    name: str = ""
    category: str = "assessment"  # assessment, formative, presentation
    auto_graded: bool = True

    @abstractmethod
    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        O'qituvchi yoki AI tomonidan kiritilgan variantlar va to'g'ri javob kalitini tekshiradi.
        Xato bo'lsa QuestionValidationError chiqarishi shart.
        """
        pass

    @abstractmethod
    def check_answer(self, user_answer: Any, correct_answer: Any, **kwargs) -> Dict[str, Any]:
        """
        Talabaning javobini to'g'ri javob kaliti bilan solishtiradi.
        Qaytaradi:
            - is_correct (bool): Javob butunlay yoki qisman to'g'rimi
            - score_ratio (float): 0.0 dan 1.0 gacha to'plangan ball koeffitsienti
            - feedback (str): Qisqa izoh yoki natija xabari
        """
        pass

    def sanitize_for_student(self, options: List[Any]) -> List[Any]:
        """
        Zero-Knowledge tamoyili: O'quvchi qurilmasiga yuborishdan oldin
        variantlardan har qanday to'g'ri javob kaliti yoki 'is_correct' bayroqlarini tozalash.
        """
        if not isinstance(options, list):
            return []
        sanitized = []
        for opt in options:
            if isinstance(opt, dict):
                clean_opt = {k: v for k, v in opt.items() if k not in ("is_correct", "correct", "score")}
                sanitized.append(clean_opt)
            else:
                sanitized.append(opt)
        return sanitized
