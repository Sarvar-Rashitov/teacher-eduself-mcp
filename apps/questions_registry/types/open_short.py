import string
from typing import Any
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Computes Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


class OpenShortQuestionType(BaseQuestionType):
    """
    Open Short / Short Text question type (Qisqa matnli javob / Type Answer).
    Validates typed answers with normalization, whitespace trimming,
    punctuation stripping, and optional Levenshtein typo tolerance.
    """

    type_id = "open_short"
    aliases = ("short_text", "type_answer")
    display_name = "Short Text Answer"
    category = "Assessment"
    requires_answer_key = True
    auto_evaluable = True

    def validate_payload(self, options: Any, correct_answer: Any, **kwargs) -> None:
        accepted = self._extract_accepted_answers(correct_answer)
        if not accepted:
            raise QuestionValidationError(
                "Short text questions require at least one accepted answer in correct_answer."
            )

        if not any(str(ans).strip() for ans in accepted):
            raise QuestionValidationError("All accepted answers are empty.")

    def check_answer(
        self,
        submission: Any,
        correct_answer: Any,
        options: Any = None,
        **kwargs
    ) -> EvaluationResult:
        submitted_text = self._extract_submitted_text(submission)
        accepted_answers = self._extract_accepted_answers(correct_answer)

        # Options configuration
        config = options if isinstance(options, dict) else {}
        case_sensitive = config.get("case_sensitive", False)
        trim_whitespace = config.get("trim_whitespace", True)
        ignore_punctuation = config.get("ignore_punctuation", True)
        allow_typos = int(config.get("allow_typos_levenshtein", 1))

        norm_submitted = self._normalize(
            submitted_text,
            case_sensitive=case_sensitive,
            trim_whitespace=trim_whitespace,
            ignore_punctuation=ignore_punctuation
        )

        is_match = False
        matched_answer = None

        for target in accepted_answers:
            norm_target = self._normalize(
                target,
                case_sensitive=case_sensitive,
                trim_whitespace=trim_whitespace,
                ignore_punctuation=ignore_punctuation
            )
            # Exact normalized match
            if norm_submitted == norm_target:
                is_match = True
                matched_answer = target
                break

            # Levenshtein typo allowance (for words >= 4 letters)
            if allow_typos > 0 and len(norm_target) >= 4:
                dist = _levenshtein_distance(norm_submitted, norm_target)
                if dist <= allow_typos:
                    is_match = True
                    matched_answer = target
                    break

        score_fraction = 1.0 if is_match else 0.0

        return EvaluationResult(
            is_correct=is_match,
            score_fraction=score_fraction,
            feedback="Correct!" if is_match else "Incorrect answer.",
            details={
                "submitted_raw": submitted_text,
                "submitted_normalized": norm_submitted,
                "matched_answer": matched_answer,
            }
        )

    def _normalize(
        self,
        text: str,
        case_sensitive: bool = False,
        trim_whitespace: bool = True,
        ignore_punctuation: bool = True
    ) -> str:
        s = str(text or "")
        if trim_whitespace:
            s = s.strip()
        if not case_sensitive:
            s = s.lower()
        if ignore_punctuation:
            # Strip standard punctuation
            translator = str.maketrans("", "", string.punctuation + "«»“”‘’—–")
            s = s.translate(translator)
            if trim_whitespace:
                # Collapse inner multi-spaces
                s = " ".join(s.split())
        return s

    def _extract_accepted_answers(self, val: Any) -> list[str]:
        if isinstance(val, dict):
            raw = val.get("accepted_answers") or val.get("answers") or val.get("correct_answer")
            if isinstance(raw, list):
                return [str(x) for x in raw if str(x).strip()]
            if raw is not None:
                return [str(raw)]
        elif isinstance(val, list):
            return [str(x) for x in val if str(x).strip()]
        elif val is not None:
            s = str(val).strip()
            return [s] if s else []
        return []

    def _extract_submitted_text(self, val: Any) -> str:
        if isinstance(val, dict):
            return str(val.get("text") or val.get("answer") or val.get("submitted_text") or "")
        if val is not None:
            return str(val)
        return ""
