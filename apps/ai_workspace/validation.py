"""
AI Content Validation & Deterministic Heuristics.
Spetsifikatsiya: .docs/ai/AI_VALIDATION.md
"""
from typing import List, Dict, Any, Optional
from apps.ai_workspace.schemas import AIGeneratedQuiz, AIGeneratedQuestion


class ContentValidationError(Exception):
    """Pedagogik yoki mantiqiy validatsiya xatosi."""
    pass


class ContentValidator:
    """
    3 bosqichli kontent tekshiruvchi dvigatel.
    AI_VALIDATION.md 2-bo'lim.
    """
    FORBIDDEN_PHRASES = [
        "barchasi to'g'ri",
        "barchasi togri",
        "yuqoridagilarning barchasi",
        "hech biri to'g'ri emas",
        "hech biri togri emas",
        "a va b javoblar",
        "b va c javoblar",
        "barcha javoblar to'g'ri",
        "все вышеперечисленное",
        "ни один из вышеперечисленных",
        "all of the above",
        "none of the above",
    ]

    @classmethod
    def validate_question(cls, q: AIGeneratedQuestion) -> List[str]:
        """Bitta savol uchun barcha evristik qoidalarni tekshirish."""
        errors = []

        # 1. Answer Key Integrity
        option_ids = {opt.id for opt in q.options}
        if isinstance(q.correct_answer, str):
            if q.correct_answer not in option_ids:
                errors.append(f"To'g'ri javob '{q.correct_answer}' variantlar ichida topilmadi.")
        elif isinstance(q.correct_answer, list):
            for ans in q.correct_answer:
                if str(ans) not in option_ids:
                    errors.append(f"To'g'ri javob '{ans}' variantlar ichida topilmadi.")

        # 2. Duplicate Options
        texts = [opt.text.strip().lower() for opt in q.options]
        if len(texts) != len(set(texts)):
            errors.append("Savolda bir xil matnli takroriy variantlar mavjud.")

        # 3. Forbidden Answer Patterns
        for opt in q.options:
            opt_lower = opt.text.lower()
            for forbidden in cls.FORBIDDEN_PHRASES:
                if forbidden in opt_lower:
                    errors.append(f"Variantda taqiqlangan noaniq ibora ishlatilgan: '{opt.text}'")
                    break

        # 4. Length Bias (To'g'ri javob boshqa variantlardan 3x uzunroq bo'lmasligi kerak)
        correct_opt = next((opt for opt in q.options if opt.id == q.correct_answer), None)
        other_opts = [opt for opt in q.options if opt.id != q.correct_answer]
        if correct_opt and other_opts:
            avg_other_len = sum(len(opt.text) for opt in other_opts) / len(other_opts)
            if avg_other_len > 0 and len(correct_opt.text) >= (avg_other_len * 3.5):
                errors.append(f"To'g'ri javob varianti boshqalardan haddan tashqari uzun (Length Bias).")

        return errors

    @classmethod
    def validate_quiz(cls, quiz: AIGeneratedQuiz) -> Dict[int, List[str]]:
        """Butun viktorina savollarini tekshirib, xatoliklar xaritasini qaytarish."""
        issues: Dict[int, List[str]] = {}
        for q in quiz.questions:
            q_errors = cls.validate_question(q)
            if q_errors:
                issues[q.order] = q_errors
        return issues

    @classmethod
    def is_valid(cls, quiz: AIGeneratedQuiz) -> bool:
        return len(cls.validate_quiz(quiz)) == 0
