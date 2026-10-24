from typing import Any, Dict, List
from ..base import BaseQuestionType
from ..exceptions import QuestionValidationError


class SingleChoiceQuestion(BaseQuestionType):
    """
    Yagona tanlovli test (Single Choice).
    2 dan 6 tagacha variant va aynan 1 ta to'g'ri javob.
    """

    type_id = "single_choice"
    name = "Yagona tanlovli test"
    category = "assessment"
    auto_graded = True

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        if not isinstance(options, list):
            raise QuestionValidationError("Variantlar (options) ro'yxat bo'lishi shart.")

        if len(options) < 2 or len(options) > 6:
            raise QuestionValidationError(f"Variantlar soni 2 dan 6 tagacha bo'lishi kerak. Hozir: {len(options)}")

        option_ids = set()
        for i, opt in enumerate(options):
            if not isinstance(opt, dict):
                raise QuestionValidationError(f"Har bir variant lug'at (dict) bo'lishi kerak: {opt}")
            opt_id = opt.get("id")
            opt_text = opt.get("text")
            if not opt_id or opt_text is None:
                raise QuestionValidationError(f"Variant {i+1} da 'id' va 'text' maydonlari to'ldirilishi shart.")
            if opt_id in option_ids:
                raise QuestionValidationError(f"Takroriy variant ID si aniqlandi: '{opt_id}'")
            option_ids.add(opt_id)

        if not correct_answer:
            raise QuestionValidationError("To'g'ri javob (correct_answer) ko'rsatilishi shart.")

        target_id = str(correct_answer.get("id") if isinstance(correct_answer, dict) else correct_answer)
        if target_id not in option_ids:
            raise QuestionValidationError(
                f"To'g'ri javob kaliti '{target_id}' mavjud variantlar orasida topilmadi: {list(option_ids)}"
            )

        return True

    def check_answer(self, user_answer: Any, correct_answer: Any, **kwargs) -> Dict[str, Any]:
        if user_answer is None:
            return {"is_correct": False, "score_ratio": 0.0, "feedback": "Javob kiritilmadi"}

        target_correct = str(correct_answer.get("id") if isinstance(correct_answer, dict) else correct_answer)
        user_choice = str(user_answer.get("id") if isinstance(user_answer, dict) else user_answer)

        is_match = (user_choice == target_correct)
        return {
            "is_correct": is_match,
            "score_ratio": 1.0 if is_match else 0.0,
            "feedback": "To'g'ri javob!" if is_match else "Noto'g'ri javob.",
        }
