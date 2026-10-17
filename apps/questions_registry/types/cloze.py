# apps/questions_registry/types/cloze.py
from typing import Any, List, Optional
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class ClozeQuestion(BaseQuestionType):
    type_id = "cloze"
    name = "Bo'sh joylarni to'ldirish (Fill in the Blanks)"
    category = "assessment"
    description = "Matndagi [blank] bo'sh o'rinlarga to'g'ri so'zlarni yozish yoki tanlash."

    def validate_payload(self, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None) -> bool:
        blanks = correct_answer.get('blanks') if isinstance(correct_answer, dict) else correct_answer
        if not isinstance(blanks, dict) or len(blanks) == 0:
            raise QuestionValidationError("To'g'ri javobda kamida bitta 'blanks' kaliti va to'g'ri so'z bo'lishi shart.")

        for b_id, val in blanks.items():
            if not val:
                raise QuestionValidationError(f"Bo'sh joy '{b_id}' uchun to'g'ri javob kiritilmagan.")

        return True

    def sanitize_for_student(self, options: Any) -> Any:
        # Agar variantlar banki (word_bank) berilgan bo'lsa, uni uzatish
        if isinstance(options, dict) and 'word_bank' in options:
            return {'word_bank': options['word_bank']}
        if isinstance(options, list):
            return [{'id': o.get('id'), 'placeholder': o.get('placeholder', '')} for o in options]
        return []

    def _normalize(self, text: Any) -> str:
        return str(text or '').strip().lower()

    def evaluate_answer(
        self,
        submitted_answer: Any,
        correct_answer: Any,
        max_points: int = 1000,
        accepted_alternatives: Optional[List] = None
    ) -> EvaluationResult:
        sub_blanks = submitted_answer.get('blanks') if isinstance(submitted_answer, dict) else submitted_answer
        cor_blanks = correct_answer.get('blanks') if isinstance(correct_answer, dict) else correct_answer

        if not isinstance(sub_blanks, dict) or not isinstance(cor_blanks, dict):
            return EvaluationResult(is_correct=False, score=0, score_ratio=0.0)

        total_blanks = len(cor_blanks)
        if total_blanks == 0:
            return EvaluationResult(is_correct=False, score=0, score_ratio=0.0)

        correct_count = 0
        for b_id, expected_val in cor_blanks.items():
            sub_val = self._normalize(sub_blanks.get(b_id, ''))
            # Kutilgan javob string yoki list (alternativlar) bo'lishi mumkin
            if isinstance(expected_val, list):
                acceptable = [self._normalize(x) for x in expected_val]
            else:
                acceptable = [self._normalize(expected_val)]

            if sub_val in acceptable:
                correct_count += 1

        ratio = correct_count / total_blanks
        is_exact = (correct_count == total_blanks)
        score = int(round(ratio * max_points))

        return EvaluationResult(
            is_correct=is_exact,
            score=score,
            score_ratio=ratio,
            details={'correct_blanks': correct_count, 'total_blanks': total_blanks}
        )
