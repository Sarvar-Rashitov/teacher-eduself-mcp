from typing import Any, Dict, List
from ..base import BaseQuestionType
from ..exceptions import QuestionValidationError


class OrderingQuestion(BaseQuestionType):
    """
    Ketma-ketlikni joylashtirish (Puzzle / Order).
    Elementlarni to'g'ri tartibda tizish.
    """

    type_id = "ordering"
    name = "Ketma-ketlikni joylashtirish"
    category = "assessment"
    auto_graded = True

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        if not isinstance(options, list) or len(options) < 2:
            raise QuestionValidationError("Ketma-ketlik savolida kamida 2 ta element bo'lishi kerak.")

        opt_ids = {str(opt["id"]) for opt in options if isinstance(opt, dict) and "id" in opt}
        if len(opt_ids) != len(options):
            raise QuestionValidationError("Har bir element unikal 'id' ga ega bo'lishi shart.")

        if not isinstance(correct_answer, list) or len(correct_answer) != len(options):
            raise QuestionValidationError(
                "To'g'ri javob barcha elementlarning to'g'ri tartibdagi ID lar ro'yxati bo'lishi kerak."
            )

        correct_ids = [str(a.get("id") if isinstance(a, dict) else a) for a in correct_answer]
        if set(correct_ids) != opt_ids:
            raise QuestionValidationError("To'g'ri javobdagi elementlar variantlar ro'yxatiga to'liq mos kelishi shart.")

        return True

    def check_answer(self, user_answer: Any, correct_answer: Any, **kwargs) -> Dict[str, Any]:
        if not isinstance(user_answer, list) or len(user_answer) != len(correct_answer):
            return {"is_correct": False, "score_ratio": 0.0, "feedback": "Tartib to'liq emas"}

        user_order = [str(u.get("id") if isinstance(u, dict) else u) for u in user_answer]
        target_order = [str(c.get("id") if isinstance(c, dict) else c) for c in correct_answer]

        # Exact match check
        if user_order == target_order:
            return {"is_correct": True, "score_ratio": 1.0, "feedback": "Mukammal tartib!"}

        # Partial position matching
        matching_positions = sum(1 for u, t in zip(user_order, target_order) if u == t)
        score_ratio = round(matching_positions / len(target_order), 2)

        return {
            "is_correct": False,
            "score_ratio": score_ratio,
            "feedback": f"{matching_positions}/{len(target_order)} ta element o'z o'rnida joylashtirildi",
        }
