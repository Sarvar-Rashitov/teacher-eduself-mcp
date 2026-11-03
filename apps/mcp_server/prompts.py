"""
Built-in MCP Prompts Specification.
Conforms to DOC-83 (MCP_RESOURCES.md).
"""

from typing import Any, Dict, List


def get_create_lesson_quiz_prompt(subject: str, grade: str, topic: str = "") -> str:
    """
    Prompt: create-lesson-quiz
    Dars mavzusi bo'yicha sifatli viktorina yaratish ko'rsatmasi.
    """
    topic_str = f"'{topic}' mavzusida" if topic else "umumiy o'quv dasturi bo'yicha"
    return (
        f"Siz EduSelf xalqaro metodist pedagogi sifatida {grade}-sinf o'quvchilari uchun "
        f"{subject} fanidan {topic_str} 10 ta qiziqarli va Bloom taksonomiyasiga mos "
        f"savollar tayyorlang. Tayyor bo'lgach, ularni platformaga saqlash uchun "
        f"'create_quiz_draft' va 'import_questions' toollaridan foydalaning."
    )


def get_analyze_session_report_prompt(session_id: str) -> str:
    """
    Prompt: analyze-session-report
    Jonli sessiya natijalarini pedagogik chuqur tahlil qilish ko'rsatmasi.
    """
    return (
        f"'{session_id}' sessiyasi bo'yicha 'get_session_report' toolini chaqiring va olingan natijalar "
        f"asosida quyidagi 3 ta savolga batafsil javob bering:\n"
        f"1. Sinfning eng katta bo'shlig'i qaysi savollarda kuzatildi va nima sababdan?\n"
        f"2. Qaysi o'quvchilarga individual yordam ko'rsatish zarur?\n"
        f"3. Keyingi darsda ushbu mavzuni mustahkamlash uchun 3 ta amaliy tavsiya bering."
    )


def get_plan_team_activity_prompt(student_count: int, duration_minutes: int) -> str:
    """
    Prompt: plan-team-activity
    Sinf soni va vaqtiga mos jamoaviy dars rejasini tuzish ko'rsatmasi.
    """
    return (
        f"Sinfda {student_count} nafar o'quvchi bor va interaktiv faoliyat uchun {duration_minutes} daqiqa "
        f"ajratilgan. EduSelf platformasining 'create_team_game' imkoniyatidan foydalangan holda "
        f"eng samarali o'yin rejimini (Classic, Team Battle, Speed Run yoki Gold Quest) tanlang, "
        f"jamoalar sonini belgilang va dars vaqtini qadam-baqadam taqsimlang."
    )
