# apps/questions_registry/types/ordering.py
from typing import Any, List, Optional
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class OrderingQuestion(BaseQuestionType):
    type_id = "ordering"
    name = "Ketma-ketlikni joylashtirish (Puzzle/Ordering)"
    category = "assessment"
    description = "Elementlarni to'g'ri ketma-ketlikda tartiblash."

    def validate_payload(self, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None) -> bool:
        if not isinstance(options, list) or len(options) < 2:
            raise QuestionValidationError("Ketma-ketlik uchun kamida 2 ta element kerak.")

        item_ids = set()
        for idx, item in enumerate(options):
            if not isinstance(item, dict) or 'id' not in item or 'text' not in item:
                raise QuestionValidationError(f"{idx + 1}-elementda 'id' va 'text' bo'lishi shart.")
            item_ids.add(str(item['id']))

        expected_order = correct_answer.get('ordered_ids') if isinstance(correct_answer, dict) else correct_answer
        if not isinstance(expected_order, list) or len(expected_order) != len(options):
            raise QuestionValidationError("To'g'ri tartib barcha elementlarning ID larini o'z ichiga olishi shart.")

        if set(str(x) for x in expected_order) != item_ids:
            raise QuestionValidationError("To'g'ri tartibdagi ID lar variantlar ID lariga mos emas.")

        return True

    def sanitize_for_student(self, options: Any) -> Any:
        # Talabaga tartibsiz (shuffled) holda uzatish
        return [{'id': opt.get('id'), 'text': opt.get('text', '')} for opt in options]

    def evaluate_answer(
        self,
        submitted_answer: Any,
        correct_answer: Any,
        max_points: int = 1000,
        accepted_alternatives: Optional[List] = None
    ) -> EvaluationResult:
        sub_order = submitted_answer.get('ordered_ids') if isinstance(submitted_answer, dict) else submitted_answer
        cor_order = correct_answer.get('ordered_ids') if isinstance(correct_answer, dict) else correct_answer

        sub_list = [str(x) for x in (sub_order or [])]
        cor_list = [str(x) for x in (cor_order or [])]

        if len(sub_list) != len(cor_list):
            return EvaluationResult(is_correct=False, score=0, score_ratio=0.0)

        # To'g'ri joyda turgan elementlar soni (Position match)
        correct_positions = sum(1 for s, c in zip(sub_list, cor_list) if s == c)
        total = len(cor_list)
        ratio = correct_positions / total if total > 0 else 0.0

        is_exact = (sub_list == cor_list)
        score = max_points if is_exact else int(round(ratio * max_points * 0.8))  # Qisman ball

        return EvaluationResult(
            is_correct=is_exact,
            score=score,
            score_ratio=ratio,
            details={'correct_positions': correct_positions, 'total': total}
        )
