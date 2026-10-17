# apps/questions_registry/types/single_choice.py
from typing import Any, List, Optional
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class SingleChoiceQuestion(BaseQuestionType):
    type_id = "single_choice"
    name = "Yagona tanlovli test (Single Choice)"
    category = "assessment"
    description = "2 dan 6 tagacha variant, aynan 1 ta to'g'ri javob."

    def validate_payload(self, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None) -> bool:
        if not isinstance(options, list) or len(options) < 2 or len(options) > 6:
            raise QuestionValidationError("Variantlar soni 2 dan 6 tagacha bo'lishi shart.")

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or 'id' not in opt or 'text' not in opt:
                raise QuestionValidationError(f"{idx + 1}-variantda 'id' va 'text' maydonlari bo'lishi shart.")
            if opt['id'] in option_ids:
                raise QuestionValidationError(f"Takrorlangan variant ID: '{opt['id']}'")
            option_ids.add(opt['id'])

        correct_id = correct_answer.get('selected_option_id') if isinstance(correct_answer, dict) else correct_answer
        if not correct_id or str(correct_id) not in option_ids:
            raise QuestionValidationError(f"To'g'ri javob ID '{correct_id}' variantlar orasida topilmadi.")

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
        sub_id = submitted_answer.get('selected_option_id') if isinstance(submitted_answer, dict) else submitted_answer
        cor_id = correct_answer.get('selected_option_id') if isinstance(correct_answer, dict) else correct_answer

        is_correct = str(sub_id) == str(cor_id)
        score = max_points if is_correct else 0
        ratio = 1.0 if is_correct else 0.0

        return EvaluationResult(
            is_correct=is_correct,
            score=score,
            score_ratio=ratio,
            details={'submitted': sub_id, 'expected': cor_id}
        )
