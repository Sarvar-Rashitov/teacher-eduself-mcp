from typing import Any, Dict, List
from ..base import BaseQuestionType
from ..exceptions import QuestionValidationError


class MultipleChoiceQuestion(BaseQuestionType):
    """
    Ko'p tanlovli test (Multiple Choice / Multiple Select).
    Kamida 3 ta variant va kamida 1 ta (odatda 2+) to'g'ri javob.
    Qisman ball (Partial credit with penalty) qo'llab-quvvatlanadi.
    """

    type_id = "multiple_choice"
    name = "Ko'p tanlovli test"
    category = "assessment"
    auto_graded = True

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        if not isinstance(options, list) or len(options) < 3:
            raise QuestionValidationError("Ko'p tanlovli savolda kamida 3 ta variant bo'lishi kerak.")

        option_ids = set()
        for i, opt in enumerate(options):
            if not isinstance(opt, dict) or not opt.get("id"):
                raise QuestionValidationError(f"Har bir variant lug'at va 'id' ga ega bo'lishi shart.")
            option_ids.add(str(opt["id"]))

        if not isinstance(correct_answer, list) or len(correct_answer) == 0:
            raise QuestionValidationError("To'g'ri javob (correct_answer) bo'sh bo'lmagan ro'yxat bo'lishi shart.")

        for ans in correct_answer:
            ans_id = str(ans.get("id") if isinstance(ans, dict) else ans)
            if ans_id not in option_ids:
                raise QuestionValidationError(f"To'g'ri javob '{ans_id}' variantlar orasida mavjud emas.")

        return True

    def check_answer(self, user_answer: Any, correct_answer: Any, **kwargs) -> Dict[str, Any]:
        if not isinstance(user_answer, list) or len(user_answer) == 0:
            return {"is_correct": False, "score_ratio": 0.0, "feedback": "Variantlar tanlanmadi"}

        correct_ids = {str(a.get("id") if isinstance(a, dict) else a) for a in correct_answer}
        user_ids = {str(u.get("id") if isinstance(u, dict) else u) for u in user_answer}

        true_positives = len(user_ids.intersection(correct_ids))
        false_positives = len(user_ids.difference(correct_ids))

        # Partial credit formula: (TP / Total_Correct) - (FP / Total_Wrong)
        total_correct = len(correct_ids)
        total_options = kwargs.get("total_options", len(correct_ids) + 2)
        total_wrong = max(1, total_options - total_correct)

        ratio = (true_positives / total_correct) - (false_positives / total_wrong)
        score_ratio = max(0.0, min(1.0, round(ratio, 2)))

        is_correct = (score_ratio == 1.0)
        return {
            "is_correct": is_correct,
            "score_ratio": score_ratio,
            "feedback": "To'liq to'g'ri!" if is_correct else (f"Qisman to'g'ri ({int(score_ratio*100)}%)" if score_ratio > 0 else "Noto'g'ri."),
        }
