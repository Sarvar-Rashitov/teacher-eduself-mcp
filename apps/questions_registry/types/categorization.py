from typing import Any
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class CategorizationQuestionType(BaseQuestionType):
    """
    Categorization / Category Sort question type (Kategoriyalarga ajratish).
    Distributes items into distinct buckets / categories.
    """

    type_id = "categorization"
    aliases = ("category_sort", "matching_categories")
    display_name = "Category Sort"
    category = "Assessment"
    requires_answer_key = True
    auto_evaluable = True

    def validate_payload(self, options: Any, correct_answer: Any, **kwargs) -> None:
        if not isinstance(options, dict):
            raise QuestionValidationError(
                "'options' for categorization must be a dictionary with 'categories' and 'items'."
            )

        categories = options.get("categories")
        items = options.get("items")

        if not isinstance(categories, list) or len(categories) < 2:
            raise QuestionValidationError(
                "Categorization requires at least 2 categories in options['categories']."
            )

        if not isinstance(items, list) or len(items) < 2:
            raise QuestionValidationError(
                "Categorization requires at least 2 items in options['items']."
            )

        cat_ids = set()
        for idx, cat in enumerate(categories):
            if not isinstance(cat, dict) or not cat.get("id") or not (cat.get("title") or cat.get("text")):
                raise QuestionValidationError(
                    f"Category at index {idx} must be a dict with non-empty 'id' and 'title'."
                )
            cid = str(cat["id"]).strip()
            if cid in cat_ids:
                raise QuestionValidationError(f"Duplicate category id '{cid}' found.")
            cat_ids.add(cid)

        item_ids = set()
        for idx, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("id") or not item.get("text"):
                raise QuestionValidationError(
                    f"Item at index {idx} must be a dict with non-empty 'id' and 'text'."
                )
            iid = str(item["id"]).strip()
            if iid in item_ids:
                raise QuestionValidationError(f"Duplicate item id '{iid}' found.")
            item_ids.add(iid)

        # Validate correct_answer mapping
        mapping = self._extract_mapping(correct_answer)
        if not mapping:
            raise QuestionValidationError(
                "correct_answer must provide an 'item_category_map' mapping each item to a category."
            )

        for iid, cid in mapping.items():
            if str(iid) not in item_ids:
                raise QuestionValidationError(f"Mapped item id '{iid}' does not exist in items list.")
            if str(cid) not in cat_ids:
                raise QuestionValidationError(
                    f"Mapped category id '{cid}' for item '{iid}' does not exist in categories list."
                )

    def check_answer(
        self,
        submission: Any,
        correct_answer: Any,
        options: Any = None,
        **kwargs
    ) -> EvaluationResult:
        submitted_map = self._extract_mapping(submission)
        expected_map = self._extract_mapping(correct_answer)

        if not expected_map:
            return EvaluationResult(
                is_correct=False,
                score_fraction=0.0,
                feedback="No correct categorization map defined."
            )

        total_items = len(expected_map)
        correct_placements = 0

        for item_id, target_cat_id in expected_map.items():
            sub_cat_id = submitted_map.get(str(item_id)) or submitted_map.get(item_id)
            if sub_cat_id and str(sub_cat_id).strip() == str(target_cat_id).strip():
                correct_placements += 1

        score_fraction = round(correct_placements / total_items, 4)
        is_perfect = (score_fraction == 1.0)

        return EvaluationResult(
            is_correct=is_perfect,
            score_fraction=score_fraction,
            feedback="All items placed correctly!" if is_perfect else (
                f"{correct_placements}/{total_items} items placed correctly."
            ),
            details={
                "correct_placements": correct_placements,
                "total_items": total_items,
                "submitted": submitted_map,
                "expected": expected_map,
            }
        )

    def _extract_mapping(self, val: Any) -> dict[str, str]:
        if isinstance(val, dict):
            raw = val.get("item_category_map") or val.get("answers") or val.get("mapping")
            if isinstance(raw, dict):
                return {str(k): str(v) for k, v in raw.items()}
            # If the dict itself is the map (excluding other keys)
            if "item_category_map" not in val and "answers" not in val:
                return {str(k): str(v) for k, v in val.items()}
        return {}
