"""
Internal Platform Tools for AI Agent.
Spetsifikatsiya: .docs/ai/AI_TOOL_CALLING.md
"""
from typing import Dict, Any, List, Optional
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.quizzes.models import Quiz, Question
from apps.ai_workspace.schemas import AIGeneratedQuiz, QuizRequirements
from apps.ai_workspace.diff_engine import AIDiffEngine

User = get_user_model()


class PlatformTools:
    """
    AI agentning platforma ichidagi ruxsat etilgan xizmatlari (Tool Calling).
    """

    @classmethod
    def suggest_game_modes(
        cls,
        student_count: int = 20,
        duration_minutes: int = 15,
        learning_goal: str = "general"
    ) -> List[Dict[str, Any]]:
        """
        AI_TOOL_CALLING.md 2.2: O'yin rejimlarini dars parametrlariga qarab tavsiya etish.
        """
        recommendations = []
        if student_count >= 15:
            recommendations.append({
                "mode": "team_battle",
                "name": "Jamoaviy Jang",
                "reason": f"Sinfda {student_count} ta o'quvchi bor, jamoaviy raqobat hamkorlikni oshiradi."
            })

        if duration_minutes <= 10:
            recommendations.append({
                "mode": "speed_run",
                "name": "Vaqt Poygasi",
                "reason": f"Dars yakuniga atigi {duration_minutes} daqiqa qolgan, tezkor blitz test mos keladi."
            })
        else:
            recommendations.append({
                "mode": "classic",
                "name": "Klassik Viktorina",
                "reason": "Har qanday mavzuni o'zlashtirishni tekshirish uchun universal standart."
            })

        recommendations.append({
            "mode": "gold_quest",
            "name": "Oltin Qidiruvi (Gold Quest)",
            "reason": "O'quvchilar motivatsiyasini oshirish uchun strategik sandiqlar va resurs to'plash."
        })

        return recommendations

    @classmethod
    @transaction.atomic
    def create_quiz_draft(
        cls,
        spec: AIGeneratedQuiz,
        author: Any
    ) -> Quiz:
        """
        AI_TOOL_CALLING.md 2.3: Yangi test draftini Universal Quiz Model'ga saqlash.
        """
        quiz = Quiz.objects.create(
            title=spec.title,
            description=spec.description,
            subject=spec.subject,
            grade_level=spec.grade_level,
            locale=spec.language,
            status='draft',
            owner=author
        )

        for q_data in spec.questions:
            # Pydantic AIGeneratedOption larini JSON dict ro'yxatiga o'girish
            options_dict = [{"id": opt.id, "text": opt.text} for opt in q_data.options]
            correct_val = q_data.correct_answer
            if isinstance(correct_val, str):
                correct_dict = {"selected_option_id": correct_val}
            elif isinstance(correct_val, list):
                correct_dict = {"selected_option_ids": correct_val}
            else:
                correct_dict = correct_val

            Question.objects.create(
                quiz=quiz,
                order_index=q_data.order,
                type=q_data.type,
                prompt=q_data.prompt,
                options=options_dict,
                correct_answer=correct_dict,
                explanation=q_data.explanation,
                time_limit_seconds=q_data.time_limit_seconds,
                points=q_data.points,
                is_locked=False
            )

        return quiz
