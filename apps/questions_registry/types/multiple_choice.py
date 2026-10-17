# apps/questions_registry/types/multiple_choice.py
from typing import Any, List, Optional
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class MultipleChoiceQuestion(BaseQuestionType):
    type_id = "multiple_choice"
    name = "Ko'p tanlovli test (Multiple Select)"
    category = "assessment"
    description = "Kamida 2 ta variant, bir nechta to'g'ri javob, qisman ball berish tizimi."

    def validate_payload(self, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None) -> bool:
        if not isinstance(options, list) or len(options) < 2:
            raise QuestionValidationError("Variantlar soni kamida 2 ta bo'lishi shart.")

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or 'id' not in opt or 'text' not in opt:
                raise QuestionValidationError(f"{idx + 1}-variantda 'id' va 'text' maydonlari bo'lishi shart.")
            option_ids.add(str(opt['id']))

        correct_ids = correct_answer.get('selected_option_ids') if isinstance(correct_answer, dict) else correct_answer
        if not isinstance(correct_ids, list) or len(correct_ids) == 0:
            raise QuestionValidationError("Kamida bitta to'g'ri javob ID ko'rsatilishi shart.")

        for cid in correct_ids:
            if str(cid) not in option_ids:
                raise QuestionValidationError(f"To'g'ri javob ID '{cid}' variantlar ro'yxatida topilmadi.")

        return True

    def sanitize_for_student(self, options: Any) -> Any:
        sanitized = []
        for opt in options:
            item = {
                'id': opt.get('id'),
                'text': opt.get('text', ''),
            }
            if 'media_url' in opt and opt['media_url']:
                item['media_url'] = opt['media_url']
            sanitized.append(item)
        return sanitized

    def evaluate_answer(
        self,
        submitted_answer: Any,
        correct_answer: Any,
        max_points: int = 1000,
        accepted_alternatives: Optional[List] = None
    ) -> EvaluationResult:
        sub_list = submitted_answer.get('selected_option_ids') if isinstance(submitted_answer, dict) else submitted_answer
        cor_list = correct_answer.get('selected_option_ids') if isinstance(correct_answer, dict) else correct_answer

        sub_set = set(str(x) for x in (sub_list or []))
        cor_set = set(str(x) for x in (cor_list or []))

        if not cor_set:
            return EvaluationResult(is_correct=False, score=0, score_ratio=0.0)

        # To'g'ri va noto'g'ri tanlanganlar
        correct_selected = len(sub_set.intersection(cor_set))
        wrong_selected = len(sub_set.difference(cor_set))

        # QUESTION_TYPES.md §3.2: Partial credit with penalty
        # ratio = max(0, (correct_selected / total_correct) - (wrong_selected / total_wrong_options))
        ratio = correct_selected / len(cor_set)
        if wrong_selected > 0:
            ratio = max(0.0, ratio - (wrong_selected * 0.5))

        ratio = min(1.0, max(0.0, ratio))
        score = int(round(ratio * max_points))
        is_full_correct = (sub_set == cor_set)

        return EvaluationResult(
            is_correct=is_full_correct,
            score=score,
            score_ratio=ratio,
            details={
                'correct_selected': correct_selected,
                'wrong_selected': wrong_selected,
                'total_expected': len(cor_set)
            }
        )
