from typing import Any, Dict, List
from ..base import BaseQuestionType
from ..exceptions import QuestionValidationError


class CategorizationQuestion(BaseQuestionType):
    """
    Kategoriyalarga ajratish (Category Sort / Categorization).
    Elementlarni bir nechta guruhlar/toifalarga ajratish.
    """

    type_id = "categorization"
    name = "Kategoriyalarga ajratish"
    category = "assessment"
    auto_graded = True

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        # options: {"categories": [...], "items": [...]} yoki list
        if not isinstance(correct_answer, dict) or len(correct_answer) < 2:
            raise QuestionValidationError(
                "To'g'ri javob kamida 2 ta toifadan iborat lug'at ({kategoriya: [elementlar]}) bo'lishi kerak."
            )

        for cat, items in correct_answer.items():
            if not isinstance(items, list):
                raise QuestionValidationError(f"'{cat}' toifasiga tegishli elementlar ro'yxat (list) bo'lishi shart.")

        return True

    def check_answer(self, user_answer: Any, correct_answer: Any, **kwargs) -> Dict[str, Any]:
        if not isinstance(user_answer, dict):
            return {"is_correct": False, "score_ratio": 0.0, "feedback": "Kategoriyalar belgilanmadi"}

        total_items = 0
        correct_placements = 0

        for cat, correct_items in correct_answer.items():
            correct_set = {str(item.get("id") if isinstance(item, dict) else item) for item in correct_items}
            total_items += len(correct_set)

            user_items = user_answer.get(cat, [])
            user_set = {str(item.get("id") if isinstance(item, dict) else item) for item in user_items}

            # To'g'ri joylashtirilganlar
            correct_placements += len(user_set.intersection(correct_set))

        if total_items == 0:
            return {"is_correct": True, "score_ratio": 1.0, "feedback": "To'g'ri"}

        ratio = round(correct_placements / total_items, 2)
        is_all_correct = (ratio == 1.0)

        return {
            "is_correct": is_all_correct,
            "score_ratio": ratio,
            "feedback": "Barcha elementlar to'g'ri ajratildi!" if is_all_correct else f"{correct_placements}/{total_items} ta to'g'ri joylashtirildi",
        }
