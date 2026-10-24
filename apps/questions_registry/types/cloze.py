from typing import Any
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class ClozeQuestionType(BaseQuestionType):
    """
    Cloze / Fill in the Blanks question type (Bo‘sh joylarni to‘ldirish).
    Validates multiple fill-in-the-blank placeholders against accepted terms.
    """

    type_id = "cloze"
    aliases = ("fill_in_blanks", "cloze_deletion")
    display_name = "Fill in the Blanks"
    category = "Assessment"
    requires_answer_key = True
    auto_evaluable = True

    def validate_payload(self, options: Any, correct_answer: Any, **kwargs) -> None:
        blanks = self._extract_blanks(correct_answer)
        if not blanks:
            raise QuestionValidationError(
                "Cloze questions require at least one blank definition in correct_answer['blanks']."
            )

        for blank_id, accepted in blanks.items():
            if not blank_id or not str(blank_id).strip():
                raise QuestionValidationError("Blank identifier cannot be empty.")
            if not accepted:
                raise QuestionValidationError(
                    f"Blank '{blank_id}' must define at least one accepted answer."
                )
            if isinstance(accepted, list):
                if not any(str(ans).strip() for ans in accepted):
                    raise QuestionValidationError(f"Blank '{blank_id}' has empty accepted answers.")
            elif not str(accepted).strip():
                raise QuestionValidationError(f"Blank '{blank_id}' has an empty accepted answer.")

    def check_answer(
        self,
        submission: Any,
        correct_answer: Any,
        options: Any = None,
        **kwargs
    ) -> EvaluationResult:
        submitted_answers = self._extract_submitted_answers(submission)
        expected_blanks = self._extract_blanks(correct_answer)

        if not expected_blanks:
            return EvaluationResult(
                is_correct=False,
                score_fraction=0.0,
                feedback="No correct answers configured for blanks."
            )

        total_blanks = len(expected_blanks)
        correct_count = 0
        blank_results = {}

        for blank_id, accepted in expected_blanks.items():
            student_val = str(submitted_answers.get(str(blank_id), "")).strip().lower()
            accepted_list = [str(a).strip().lower() for a in accepted] if isinstance(accepted, list) else [str(accepted).strip().lower()]

            if student_val in accepted_list:
                correct_count += 1
                blank_results[blank_id] = True
            else:
                blank_results[blank_id] = False

        score_fraction = round(correct_count / total_blanks, 4)
        is_perfect = (score_fraction == 1.0)

        return EvaluationResult(
            is_correct=is_perfect,
            score_fraction=score_fraction,
            feedback="All blanks filled correctly!" if is_perfect else f"{correct_count}/{total_blanks} blanks correct.",
            details={
                "correct_blanks": correct_count,
                "total_blanks": total_blanks,
                "blank_results": blank_results,
                "submitted": submitted_answers,
            }
        )

    def _extract_blanks(self, val: Any) -> dict[str, list[str]]:
        if isinstance(val, dict):
            raw = val.get("blanks")
            if isinstance(raw, dict):
                result = {}
                for k, v in raw.items():
                    if isinstance(v, list):
                        result[str(k)] = [str(x) for x in v if str(x).strip()]
                    elif v is not None:
                        result[str(k)] = [str(v)]
                return result
            # Or dict itself is blank -> answers
            if "blanks" not in val and all(isinstance(v, (str, list)) for v in val.values()):
                result = {}
                for k, v in val.items():
                    if isinstance(v, list):
                        result[str(k)] = [str(x) for x in v if str(x).strip()]
                    elif v is not None:
                        result[str(k)] = [str(v)]
                return result
        return {}

    def _extract_submitted_answers(self, val: Any) -> dict[str, str]:
        if isinstance(val, dict):
            raw = val.get("answers") or val.get("blanks")
            if isinstance(raw, dict):
                return {str(k): str(v) for k, v in raw.items()}
            return {str(k): str(v) for k, v in val.items()}
        return {}
