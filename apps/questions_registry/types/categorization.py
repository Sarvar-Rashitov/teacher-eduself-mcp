# apps/questions_registry/types/categorization.py
from typing import Any, List, Optional
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class CategorizationQuestion(BaseQuestionType):
    type_id = "categorization"
    name = "Kategoriyalarga ajratish (Category Sort)"
    category = "assessment"
    description = "Elementlarni tegishli guruh/kategoriyalarga taqsimlash."

    def validate_payload(self, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None) -> bool:
        if not isinstance(options, dict):
            raise QuestionValidationError("Variantlar 'categories' va 'items' obyektidan iborat bo'lishi shart.")

        categories = options.get('categories', [])
        items = options.get('items', [])

        if not isinstance(categories, list) or len(categories) < 2:
            raise QuestionValidationError("Kamida 2 ta kategoriya bo'lishi shart.")

        if not isinstance(items, list) or len(items) < 2:
            raise QuestionValidationError("Kamida 2 ta ajratiladigan element bo'lishi shart.")

        cat_ids = {str(c['id']) for c in categories if isinstance(c, dict) and 'id' in c}
        item_ids = {str(i['id']) for i in items if isinstance(i, dict) and 'id' in i}

        mapping = correct_answer.get('mapping') if isinstance(correct_answer, dict) else correct_answer
        if not isinstance(mapping, dict):
            raise QuestionValidationError("To'g'ri javob 'mapping' (element_id -> category_id) bo'lishi shart.")

        for i_id, c_id in mapping.items():
            if str(i_id) not in item_ids:
                raise QuestionValidationError(f"Mappingdagi element ID '{i_id}' items ro'yxatida yo'q.")
            if str(c_id) not in cat_ids:
                raise QuestionValidationError(f"Mappingdagi kategoriya ID '{c_id}' categories ro'yxatida yo'q.")

        return True

    def sanitize_for_student(self, options: Any) -> Any:
        # Kategoriyalar va elementlarni toza ko'rinishda uzatish
        return {
            'categories': [{'id': c.get('id'), 'name': c.get('name', '')} for c in options.get('categories', [])],
            'items': [{'id': i.get('id'), 'text': i.get('text', '')} for i in options.get('items', [])]
        }

    def evaluate_answer(
        self,
        submitted_answer: Any,
        correct_answer: Any,
        max_points: int = 1000,
        accepted_alternatives: Optional[List] = None
    ) -> EvaluationResult:
        sub_map = submitted_answer.get('mapping') if isinstance(submitted_answer, dict) else submitted_answer
        cor_map = correct_answer.get('mapping') if isinstance(correct_answer, dict) else correct_answer

        if not isinstance(sub_map, dict) or not isinstance(cor_map, dict):
            return EvaluationResult(is_correct=False, score=0, score_ratio=0.0)

        total_items = len(cor_map)
        if total_items == 0:
            return EvaluationResult(is_correct=False, score=0, score_ratio=0.0)

        correct_count = 0
        for i_id, expected_cat in cor_map.items():
            if str(sub_map.get(str(i_id))) == str(expected_cat):
                correct_count += 1

        ratio = correct_count / total_items
        is_exact = (correct_count == total_items)
        score = int(round(ratio * max_points))

        return EvaluationResult(
            is_correct=is_exact,
            score=score,
            score_ratio=ratio,
            details={'correct_count': correct_count, 'total_items': total_items}
        )
