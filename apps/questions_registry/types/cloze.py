from typing import Any, Dict, List
from ..base import BaseQuestionType
from ..exceptions import QuestionValidationError


class ClozeQuestion(BaseQuestionType):
    """
    Bo'sh joylarni to'ldirish (Fill in the blanks / Cloze).
    Matndagi bo'shliqlarga to'g'ri so'z yoki iboralarni kiritish.
    """

    type_id = "cloze"
    name = "Bo'sh joylarni to'ldirish"
    category = "assessment"
    auto_graded = True

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        if not isinstance(correct_answer, (dict, list)) or len(correct_answer) == 0:
            raise QuestionValidationError(
                "Cloze savolida to'g'ri javoblar bo'sh bo'lmagan lug'at yoki ro'yxat bo'lishi kerak."
            )
        return True

    def check_answer(self, user_answer: Any, correct_answer: Any, **kwargs) -> Dict[str, Any]:
        if not isinstance(user_answer, (dict, list)):
            return {"is_correct": False, "score_ratio": 0.0, "feedback": "Bo'shliqlar to'ldirilmadi"}

        # Lug'at formatiga keltirish
        user_dict = user_answer if isinstance(user_answer, dict) else {str(i): v for i, v in enumerate(user_answer)}
        target_dict = correct_answer if isinstance(correct_answer, dict) else {str(i): v for i, v in enumerate(correct_answer)}

        total_blanks = len(target_dict)
        if total_blanks == 0:
            return {"is_correct": True, "score_ratio": 1.0, "feedback": "To'g'ri"}

        correct_blanks = 0
        for blank_key, expected in target_dict.items():
            user_val = str(user_dict.get(blank_key, "")).strip().lower()
            if isinstance(expected, list):
                accepted = [str(e).strip().lower() for e in expected]
                if user_val in accepted:
                    correct_blanks += 1
            else:
                if user_val == str(expected).strip().lower():
                    correct_blanks += 1

        ratio = round(correct_blanks / total_blanks, 2)
        is_all_correct = (ratio == 1.0)

        return {
            "is_correct": is_all_correct,
            "score_ratio": ratio,
            "feedback": "Barcha bo'shliqlar to'g'ri to'ldirildi!" if is_all_correct else f"{correct_blanks}/{total_blanks} ta bo'shliq to'g'ri",
        }
