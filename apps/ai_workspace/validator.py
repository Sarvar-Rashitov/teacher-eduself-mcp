"""
Multi-Tier Content Validation Pipeline for AI-Generated Quizzes and Questions.
Implements:
- Tier 1: Deterministic heuristics (answer key integrity, duplicate options, forbidden phrases, length bias)
- Tier 2: Quiz-level question duplicate and overlap detection
"""

import re
from dataclasses import dataclass, field
from typing import List, Set
from .schemas import AIGeneratedQuiz, AIGeneratedQuestion, FORBIDDEN_OPTION_PATTERNS


@dataclass
class ValidationReport:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    flagged_question_orders: List[int] = field(default_factory=list)


class ContentValidator:
    """
    Validates pedagogical and structural integrity of AI generated content.
    """

    @classmethod
    def validate_question(cls, q: AIGeneratedQuestion) -> List[str]:
        """
        Runs deterministic checks on a single question.
        Returns a list of error strings (empty if valid).
        """
        errors = []

        # 1. Answer Key Integrity
        opt_ids = {opt.id for opt in q.options}
        if isinstance(q.correct_answer, str):
            if q.correct_answer not in opt_ids:
                errors.append(f"Question {q.order}: Correct answer '{q.correct_answer}' not in options {opt_ids}.")
        elif isinstance(q.correct_answer, list):
            for ans in q.correct_answer:
                if ans not in opt_ids:
                    errors.append(f"Question {q.order}: Correct answer '{ans}' not in options {opt_ids}.")

        # 2. Duplicate Option Texts
        seen_texts: Set[str] = set()
        for opt in q.options:
            norm_text = re.sub(r"\s+", " ", opt.text.strip().lower())
            if norm_text in seen_texts:
                errors.append(f"Question {q.order}: Duplicate option text '{opt.text}'.")
            seen_texts.add(norm_text)

        # 3. Forbidden Option Patterns
        for opt in q.options:
            norm_text = opt.text.strip().lower()
            for forbidden in FORBIDDEN_OPTION_PATTERNS:
                if forbidden in norm_text:
                    errors.append(
                        f"Question {q.order}: Option '{opt.id}' contains forbidden phrase '{forbidden}'."
                    )

        # 4. Length Bias Check (if correct option is > 3x average incorrect length)
        if isinstance(q.correct_answer, str) and len(q.options) >= 3:
            correct_opt = next((o for o in q.options if o.id == q.correct_answer), None)
            incorrect_opts = [o for o in q.options if o.id != q.correct_answer]
            if correct_opt and incorrect_opts:
                avg_incorrect_len = sum(len(o.text) for o in incorrect_opts) / len(incorrect_opts)
                if avg_incorrect_len > 0 and len(correct_opt.text) > (3.5 * avg_incorrect_len):
                    errors.append(
                        f"Question {q.order}: Correct option is disproportionately longer than distractors (length bias)."
                    )

        return errors

    @classmethod
    def validate_quiz(cls, quiz: AIGeneratedQuiz) -> ValidationReport:
        """
        Validates entire quiz including cross-question duplicate detection.
        """
        report = ValidationReport(is_valid=True)

        # Check each question
        for q in quiz.questions:
            q_errors = cls.validate_question(q)
            if q_errors:
                report.is_valid = False
                report.errors.extend(q_errors)
                report.flagged_question_orders.append(q.order)

        # Tier 2: Check Duplicate Questions across Quiz
        normalized_prompts = []
        for i, q in enumerate(quiz.questions):
            tokens = set(re.findall(r"\w+", q.prompt.lower()))
            for j, prev_tokens in enumerate(normalized_prompts):
                if tokens and prev_tokens:
                    intersection = len(tokens.intersection(prev_tokens))
                    overlap_ratio = intersection / min(len(tokens), len(prev_tokens))
                    if overlap_ratio >= 0.70:
                        report.is_valid = False
                        report.errors.append(
                            f"Questions {quiz.questions[j].order} and {q.order} are near-identical duplicate questions (Overlap: {overlap_ratio:.2f})."
                        )
                        if q.order not in report.flagged_question_orders:
                            report.flagged_question_orders.append(q.order)
            normalized_prompts.append(tokens)

        return report
