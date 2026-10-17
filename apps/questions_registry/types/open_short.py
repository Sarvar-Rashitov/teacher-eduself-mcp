# apps/questions_registry/types/open_short.py
from typing import Any, List, Optional
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class OpenShortQuestion(BaseQuestionType):
    type_id = "open_short"
    name = "Qisqa matnli javob (Short Text / Type Answer)"
    category = "assessment"
    description = "Foydalanuvchi qisqa matn yoki son kiritadi, normalizatsiya bilan tekshiriladi."

    def validate_payload(self, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None) -> bool:
        answer_text = correct_answer.get('text') if isinstance(correct_answer, dict) else correct_answer
        if not answer_text or not str(answer_text).strip():
            raise QuestionValidationError("Qisqa matnli savol uchun kamida bitta to'g'ri javob matni kiritilishi shart.")
        return True

    def sanitize_for_student(self, options: Any) -> Any:
        # Talabaga placeholder yoki ko'rsatma uzatish
        if isinstance(options, dict):
            return {
                'placeholder': options.get('placeholder', "Javobingizni yozing..."),
                'max_length': options.get('max_length', 100)
            }
        return {'placeholder': "Javobingizni yozing..."}

    def _normalize(self, text: Any, case_sensitive: bool = False) -> str:
        s = str(text or '').strip()
        # Tinish belgilarini olib tashlash
        for ch in [',', '.', '!', '?', ';', ':']:
            s = s.replace(ch, '')
        return s if case_sensitive else s.lower()

    def evaluate_answer(
        self,
        submitted_answer: Any,
        correct_answer: Any,
        max_points: int = 1000,
        accepted_alternatives: Optional[List] = None
    ) -> EvaluationResult:
        sub_text = submitted_answer.get('text') if isinstance(submitted_answer, dict) else submitted_answer
        cor_text = correct_answer.get('text') if isinstance(correct_answer, dict) else correct_answer

        # To'g'ri javoblar ro'yxatini shakllantirish
        valid_answers = [self._normalize(cor_text)]
        if accepted_alternatives and isinstance(accepted_alternatives, list):
            valid_answers.extend([self._normalize(alt) for alt in accepted_alternatives if alt])

        normalized_sub = self._normalize(sub_text)
        is_correct = normalized_sub in valid_answers and normalized_sub != ''

        score = max_points if is_correct else 0
        ratio = 1.0 if is_correct else 0.0

        return EvaluationResult(
            is_correct=is_correct,
            score=score,
            score_ratio=ratio,
            details={'submitted': sub_text, 'expected': cor_text, 'alternatives': accepted_alternatives or []}
        )
