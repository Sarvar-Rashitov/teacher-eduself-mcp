import re
from typing import Any, Dict, List
from ..base import BaseQuestionType
from ..exceptions import QuestionValidationError


class OpenShortQuestion(BaseQuestionType):
    """
    Qisqa matnli javob (Open Short / Type Answer / Short Text).
    Matnli kiritmani normalizatsiya qilib (trim, lowercase, tinish belgilari) tekshiradi.
    """

    type_id = "open_short"
    name = "Qisqa matnli javob"
    category = "assessment"
    auto_graded = True

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        if not correct_answer:
            raise QuestionValidationError("To'g'ri javob matni (yoki variantlari) ko'rsatilishi shart.")

        if isinstance(correct_answer, list) and len(correct_answer) == 0:
            raise QuestionValidationError("To'g'ri javoblar ro'yxati bo'sh bo'lishi mumkin emas.")

        return True

    def _normalize(self, text: str) -> str:
        """Kichik harflar, tinish belgilarini tozalash va ortiqcha bo'shliqlarni olib tashlash."""
        if not isinstance(text, str):
            text = str(text)
        # Tinish belgilarini olib tashlash
        cleaned = re.sub(r"[^\w\s]", "", text)
        return " ".join(cleaned.strip().lower().split())

    def check_answer(self, user_answer: Any, correct_answer: Any, **kwargs) -> Dict[str, Any]:
        if user_answer is None or str(user_answer).strip() == "":
            return {"is_correct": False, "score_ratio": 0.0, "feedback": "Javob yozilmadi"}

        normalized_user = self._normalize(str(user_answer))

        accepted_list = []
        if isinstance(correct_answer, list):
            accepted_list = [self._normalize(str(a)) for a in correct_answer]
        elif isinstance(correct_answer, dict):
            # Masalan, {"accepted": ["A", "B"]}
            raw_acc = correct_answer.get("accepted", [correct_answer.get("text", "")])
            accepted_list = [self._normalize(str(a)) for a in raw_acc]
        else:
            accepted_list = [self._normalize(str(correct_answer))]

        # Qo'shimcha qabul qilinadigan javoblar (synonyms/alternatives)
        accepted_alternatives = kwargs.get("accepted_alternatives", [])
        if isinstance(accepted_alternatives, list):
            for alt in accepted_alternatives:
                accepted_list.append(self._normalize(str(alt)))

        is_match = (normalized_user in accepted_list)

        return {
            "is_correct": is_match,
            "score_ratio": 1.0 if is_match else 0.0,
            "feedback": "To'g'ri javob!" if is_match else "Noto'g'ri javob.",
        }
