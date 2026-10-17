# ============================================================
# EduSelf Teacher — apps/mcp_server/prompts.py
# Pedagogical Prompt Templates for MCP
# MCP_RESOURCES.md DOC-83 asosida
# ============================================================
from typing import Dict, Any, List


def prompt_create_lesson_quiz(subject: str, grade: int, topic: str = "") -> str:
    """Dars mavzusi bo'yicha sifatli viktorina generatsiyasi uchun prompt."""
    topic_str = f"'{topic}' mavzusida" if topic else "tegishli dastur asosida"
    return f"""Siz tajribali metodist va pedagogik AI yordamchisiz.
Iltimos, {grade}-sinf o'quvchilari uchun '{subject}' fanidan {topic_str} 10 ta qiziqarli va ta'limiy jihatdan mukammal savol tuzing.

Ko'rsatmalar:
1. Har bir savol uchun 4 ta variant (bitta to'g'ri, uchtasi mantiqli chalg'ituvchi) bering.
2. Savollar oddiydan murakkabga qarab tartiblansin.
3. Barcha savollarni platformada saqlash uchun `create_quiz_draft` asbobini chaqiring.
"""


def prompt_analyze_session_report(session_id: str) -> str:
    """Jonli dars natijalarini tahlil qilish uchun prompt."""
    return f"""Iltimos, '{session_id}' identifikatorli o'tkazilgan dars sessiyasining natijalarini tahlil qiling:
1. `get_session_report(session_id='{session_id}')` asbobini chaqirib hisobotni oling.
2. Sinfning umumiy o'zlashtirish ko'rsatkichini baholang.
3. Eng ko'p xato qilingan savollarni aniqlang va o'quvchilar nega aynan shu yerda adashganini tushuntiring.
4. O'qituvchiga keyingi darsda ushbu bo'shliqlarni to'ldirish uchun 3 ta amaliy tavsiya bering.
"""


def prompt_plan_team_activity(student_count: int, duration_minutes: int) -> str:
    """Dars vaqtiga mos eng yaxshi jamoaviy rejimni tanlash bo'yicha prompt."""
    return f"""Sinfda {student_count} nafar o'quvchi bor va interaktiv faoliyat uchun {duration_minutes} daqiqa vaqt ajratilgan.
Iltimos:
1. Mavjud o'yin rejimlari (`eduself://game-modes` resursi) orasidan eng mosini tavsiya qiling (masalan: Team Battle, Gold Quest yoki Speed Run).
2. O'quvchilarni optimal nechta jamoaga bo'lish kerakligini ayting.
3. Sessiyani sozlash uchun `create_team_game` asbobini qanday chaqirish kerakligini tushuntiring.
"""
