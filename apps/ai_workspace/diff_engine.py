"""
AI Question Diff Engine & Question Lock Protection.
Spetsifikatsiya: .docs/ai/AI_AGENT.md (4 va 5-bo'lim)
"""
from typing import Dict, Any, List, Optional
from apps.quizzes.models import Question, Quiz


class QuestionLockedError(Exception):
    """Qulflangan savolga o'zgartirish kiritishga urinish xatosi."""
    pass


class AIDiffEngine:
    """
    Savollardagi o'zgarishlarni solishtirish va o'qituvchi tasdig'iga tayyorlash.
    """

    @classmethod
    def compute_question_diff(
        cls,
        original_data: Dict[str, Any],
        proposed_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Eski va yangi savolni maydonlar bo'yicha solishtirish (Side-by-Side Diff).
        """
        comparable_fields = [
            'prompt', 'options', 'correct_answer',
            'explanation', 'time_limit_seconds', 'points'
        ]

        modified_fields = []
        for field in comparable_fields:
            orig_val = original_data.get(field)
            prop_val = proposed_data.get(field)
            if orig_val != prop_val:
                modified_fields.append(field)

        has_changes = len(modified_fields) > 0

        summary = "O'zgarish yo'q" if not has_changes else f"O'zgargan maydonlar: {', '.join(modified_fields)}"

        return {
            "has_changes": has_changes,
            "modified_fields": modified_fields,
            "original": original_data,
            "proposed": proposed_data,
            "summary": summary
        }

    @classmethod
    def verify_not_locked(cls, question: Question):
        """
        AI_AGENT.md 5-bo'lim: Question Locking.
        O'qituvchi is_locked=True qilgan savolni AI o'zgartira olmaydi.
        """
        if getattr(question, 'is_locked', False):
            raise QuestionLockedError(
                f"Savol #{question.order_index} o'qituvchi tomonidan qulflangan (is_locked=True). "
                f"AI uni o'chira yoki tahrirlay olmaydi."
            )

    @classmethod
    def apply_revision(
        cls,
        question: Question,
        new_data: Dict[str, Any]
    ) -> Question:
        """
        Tasdiqlangan o'zgarishni bazadagi savolga qo'llash.
        """
        cls.verify_not_locked(question)

        if 'prompt' in new_data:
            question.prompt = new_data['prompt']
        if 'options' in new_data:
            question.options = new_data['options']
        if 'correct_answer' in new_data:
            question.correct_answer = new_data['correct_answer']
        if 'explanation' in new_data:
            question.explanation = new_data['explanation']
        if 'time_limit_seconds' in new_data:
            question.time_limit_seconds = int(new_data['time_limit_seconds'])
        if 'points' in new_data:
            question.points = int(new_data['points'])

        question.save()
        return question
