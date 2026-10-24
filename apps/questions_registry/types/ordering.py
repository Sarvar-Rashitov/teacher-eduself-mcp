from typing import Any
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class OrderingQuestionType(BaseQuestionType):
    """
    Ordering / Puzzle Order question type (Ketma-ketlikni to‘g‘ri joylashtirish).
    Items must be sorted in correct logical / chronological sequence.
    Scores using pairwise relative ordering (Kendall Tau distance).
    """

    type_id = "ordering"
    aliases = ("puzzle_order", "sequence")
    display_name = "Puzzle / Sequence Order"
    category = "Assessment"
    requires_answer_key = True
    auto_evaluable = True

    def validate_payload(self, options: Any, correct_answer: Any, **kwargs) -> None:
        if not isinstance(options, list):
            raise QuestionValidationError("'options' must be a list of sequence items.")

        if len(options) < 2:
            raise QuestionValidationError("Ordering questions require at least 2 items to sequence.")

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict):
                raise QuestionValidationError(f"Item at index {idx} must be a dictionary.")
            opt_id = opt.get("id")
            opt_text = opt.get("text")
            if not opt_id or not str(opt_id).strip():
                raise QuestionValidationError(f"Item at index {idx} must have a non-empty 'id'.")
            if opt_text is None or not str(opt_text).strip():
                raise QuestionValidationError(f"Item at index {idx} must have non-empty 'text'.")
            if opt_id in option_ids:
                raise QuestionValidationError(f"Duplicate item id '{opt_id}' found.")
            option_ids.add(opt_id)

        ordered_ids = self._extract_ordered_ids(correct_answer)
        if not ordered_ids:
            raise QuestionValidationError(
                "A non-empty 'ordered_item_ids' list must be specified in correct_answer."
            )

        if set(ordered_ids) != option_ids:
            raise QuestionValidationError(
                "The ordered_item_ids in correct_answer must contain exactly all option IDs."
            )

    def check_answer(
        self,
        submission: Any,
        correct_answer: Any,
        options: Any = None,
        **kwargs
    ) -> EvaluationResult:
        submitted_order = self._extract_ordered_ids(submission)
        correct_order = self._extract_ordered_ids(correct_answer)

        if not submitted_order or len(submitted_order) != len(correct_order):
            return EvaluationResult(
                is_correct=False,
                score_fraction=0.0,
                feedback="Submitted order does not match question item count.",
                details={"submitted": submitted_order, "expected": correct_order}
            )

        # Exact match check
        if submitted_order == correct_order:
            return EvaluationResult(
                is_correct=True,
                score_fraction=1.0,
                feedback="Perfect order!",
                details={"submitted": submitted_order, "expected": correct_order}
            )

        # Pairwise relative order comparison (Kendall Tau)
        n = len(correct_order)
        total_pairs = n * (n - 1) // 2
        if total_pairs == 0:
            fraction = 1.0 if submitted_order == correct_order else 0.0
        else:
            submitted_pos = {item_id: idx for idx, item_id in enumerate(submitted_order)}
            correct_pairs_count = 0

            for i in range(n):
                for j in range(i + 1, n):
                    first = correct_order[i]
                    second = correct_order[j]
                    if first in submitted_pos and second in submitted_pos:
                        if submitted_pos[first] < submitted_pos[second]:
                            correct_pairs_count += 1

            fraction = correct_pairs_count / total_pairs

        score_fraction = round(fraction, 4)
        is_correct = (score_fraction == 1.0)

        return EvaluationResult(
            is_correct=is_correct,
            score_fraction=score_fraction,
            feedback=f"Order partially correct ({int(score_fraction * 100)}%).",
            details={
                "submitted": submitted_order,
                "expected": correct_order,
                "correct_pairs": correct_pairs_count if total_pairs > 0 else 0,
                "total_pairs": total_pairs,
            }
        )

    def _extract_ordered_ids(self, val: Any) -> list[str]:
        if isinstance(val, dict):
            raw = val.get("ordered_item_ids") or val.get("submitted_order") or val.get("order")
            if isinstance(raw, list):
                return [str(x) for x in raw]
        elif isinstance(val, list):
            return [str(x) for x in val]
        return []
