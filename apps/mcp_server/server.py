# ============================================================
# EduSelf Teacher — apps/mcp_server/server.py
# FastMCP / MCPServer Core Instance & Registry
# MCP_SERVER.md DOC-81 va MCP_TOOLS.md DOC-82 asosida
# ============================================================
from typing import Dict, Any, List, Optional
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

import apps.mcp_server.tools as tools
import apps.mcp_server.resources as resources
import apps.mcp_server.prompts as prompts

# Server instansiyasi e'lon qilinadi
mcp_server = MCPServer(
    name="eduself-teacher-mcp",
    version="1.0.0",
    description="EduSelf Teacher Platform MCP Serveri — O'qituvchi AI Yordamchisi",
)


# ============================================================
# 1. Kategoriya: Kontent va Savollar Boshqaruvi Tools
# ============================================================
@mcp_server.tool(
    name="create_quiz_draft",
    description="Berilgan parametrlar (nom, fan, sinf) asosida yangi viktorina draftini yaratadi."
)
async def tool_create_quiz_draft(
    title: str,
    subject: str,
    grade_level: int,
    topic: str = "",
    question_count: int = 10,
    language: str = "uz",
    game_mode: str = "classic"
) -> Dict[str, Any]:
    return await tools.create_quiz_draft(
        title=title,
        subject=subject,
        grade_level=grade_level,
        topic=topic,
        question_count=question_count,
        language=language,
        game_mode=game_mode,
    )


@mcp_server.tool(
    name="get_quiz",
    description="Saqlangan viktorina va uning barcha savollarini to'liq olish."
)
async def tool_get_quiz(quiz_id: str) -> Dict[str, Any]:
    return await tools.get_quiz(quiz_id=quiz_id)


@mcp_server.tool(
    name="update_quiz",
    description="Mavjud viktorina parametrlarini yoki savollarini tahrirlash."
)
async def tool_update_quiz(quiz_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    return await tools.update_quiz(quiz_id=quiz_id, changes=changes)


@mcp_server.tool(
    name="validate_quiz",
    description="Viktorinadagi savollarning to'liqligi va to'g'ri javoblari mavjudligini tekshirish."
)
async def tool_validate_quiz(quiz_id: str) -> Dict[str, Any]:
    return await tools.validate_quiz(quiz_id=quiz_id)


@mcp_server.tool(
    name="import_questions",
    description="CSV, matn yoki JSON formatdan savollarni import qilish."
)
async def tool_import_questions(quiz_id: str, source_format: str, content: str) -> Dict[str, Any]:
    return await tools.import_questions(quiz_id=quiz_id, source_format=source_format, content=content)


@mcp_server.tool(
    name="list_question_sets",
    description="O'qituvchining saqlangan viktorinalarini qidirish va ro'yxatini olish."
)
async def tool_list_question_sets(query: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    return await tools.list_question_sets(query=query, page=page, page_size=page_size)


# ============================================================
# 2. Kategoriya: Jonli Sessiya Boshqaruvi Tools
# ============================================================
@mcp_server.tool(
    name="create_live_session",
    description="Tanlangan viktorina va o'yin rejimi bo'yicha jonli xona (PIN kod) ochadi."
)
async def tool_create_live_session(
    quiz_id: str,
    game_mode: str = "classic",
    team_mode_enabled: bool = False
) -> Dict[str, Any]:
    return await tools.create_live_session(quiz_id=quiz_id, game_mode=game_mode, team_mode_enabled=team_mode_enabled)


@mcp_server.tool(
    name="get_session_status",
    description="Jonli sessiyaning joriy holati va ulangan o'quvchilar sonini monitoring qilish."
)
async def tool_get_session_status(session_id: str) -> Dict[str, Any]:
    return await tools.get_session_status(session_id=session_id)


@mcp_server.tool(
    name="start_session",
    description="Lobbini yopib, 1-savolni ishga tushirish (O'qituvchi tasdig'i talab qilinadi).",
    annotations=ToolAnnotations(destructive_hint=True)
)
async def tool_start_session(session_id: str, confirm: bool = True) -> Dict[str, Any]:
    return await tools.start_session(session_id=session_id, confirm=confirm)


@mcp_server.tool(
    name="advance_question",
    description="Keyingi savolga o'tish."
)
async def tool_advance_question(session_id: str) -> Dict[str, Any]:
    return await tools.advance_question(session_id=session_id)


@mcp_server.tool(
    name="reveal_answers",
    description="Savolni yopib, to'g'ri javoblarni ekranda oshkor qilish (O'qituvchi tasdig'i talab qilinadi).",
    annotations=ToolAnnotations(destructive_hint=True)
)
async def tool_reveal_answers(session_id: str, confirm: bool = True) -> Dict[str, Any]:
    return await tools.reveal_answers(session_id=session_id, confirm=confirm)


@mcp_server.tool(
    name="end_session",
    description="Sessiyani yakunlash, yakuniy reytingni ko'rsatish va xonani yopish (O'qituvchi tasdig'i talab qilinadi).",
    annotations=ToolAnnotations(destructive_hint=True)
)
async def tool_end_session(session_id: str, confirm: bool = True) -> Dict[str, Any]:
    return await tools.end_session(session_id=session_id, confirm=confirm)


@mcp_server.tool(
    name="get_live_results",
    description="Joriy savol bo'yicha kimlar qanday javob bergani va peshqadamlar jadvalini olish."
)
async def tool_get_live_results(session_id: str) -> Dict[str, Any]:
    return await tools.get_live_results(session_id=session_id)


# ============================================================
# 3. Kategoriya: O'yinlar, Hisobotlar va Qo'shimcha Tools
# ============================================================
@mcp_server.tool(
    name="create_team_game",
    description="O'quvchilarni jamoalarga taqsimlab o'yin boshlash."
)
async def tool_create_team_game(
    session_id: str,
    team_count: int = 2,
    allocation_strategy: str = "random"
) -> Dict[str, Any]:
    return await tools.create_team_game(session_id=session_id, team_count=team_count, allocation_strategy=allocation_strategy)


@mcp_server.tool(
    name="create_anonymous_board",
    description="Anonim fikrlar yoki so'z buluti (Word Cloud) doskasini ishga tushirish."
)
async def tool_create_anonymous_board(session_id: str, board_title: str = "Fikrlar Doskasi") -> Dict[str, Any]:
    return await tools.create_anonymous_board(session_id=session_id, board_title=board_title)


@mcp_server.tool(
    name="get_session_report",
    description="Sessiya yakunlangach, sinfning umumiy o'zlashtirishi va eng ko'p xato qilingan savollar tahlilini olish."
)
async def tool_get_session_report(session_id: str) -> Dict[str, Any]:
    return await tools.get_session_report(session_id=session_id)


@mcp_server.tool(
    name="generate_followup_activity",
    description="O'quvchilar ko'p adashgan mavzular bo'yicha keyingi dars uchun avtomatik mustahkamlovchi mini-viktorina yaratish."
)
async def tool_generate_followup_activity(session_id: str, question_count: int = 5) -> Dict[str, Any]:
    return await tools.generate_followup_activity(session_id=session_id, question_count=question_count)


@mcp_server.tool(
    name="export_results",
    description="Jonli sessiya o'quvchilar natijalarini to'liq eksport qilish."
)
async def tool_export_results(session_id: str, export_format: str = "json") -> Dict[str, Any]:
    return await tools.export_results(session_id=session_id, export_format=export_format)


# ============================================================
# Tizim Resurslari (MCP Resources)
# ============================================================
@mcp_server.resource(
    "eduself://question-types",
    description="Platformadagi barcha 29 ta savol turlari, cheklovlar va JSON sxemalari"
)
def res_question_types() -> str:
    return resources.get_question_types_resource()


@mcp_server.resource(
    "eduself://game-modes",
    description="Platformadagi barcha 50 ta o'yin rejimlari va ularning qoidalari"
)
def res_game_modes() -> str:
    return resources.get_game_modes_resource()


@mcp_server.resource(
    "eduself://teacher-guide",
    description="Darsda interaktiv viktorinalarni o'tkazish bo'yicha metodik qo'llanma"
)
def res_teacher_guide() -> str:
    return resources.get_teacher_guide_resource()


@mcp_server.resource(
    "eduself://session/{session_id}/summary",
    description="Jonli sessiyaning joriy holati va xulosasi"
)
async def res_session_summary(session_id: str) -> str:
    return await resources.get_session_summary_resource(session_id)


# ============================================================
# Pedagogik Prompt Shablonlari (MCP Prompts)
# ============================================================
@mcp_server.prompt(
    "create-lesson-quiz",
    description="Dars mavzusi bo'yicha 10 ta pedagogik savol tuzish va draft yaratish"
)
def prompt_quiz(subject: str, grade: int, topic: str = "") -> str:
    return prompts.prompt_create_lesson_quiz(subject=subject, grade=grade, topic=topic)


@mcp_server.prompt(
    "analyze-session-report",
    description="O'tkazilgan dars sessiyasi hisobotini tahlil qilish va tavsiyalar olish"
)
def prompt_report(session_id: str) -> str:
    return prompts.prompt_analyze_session_report(session_id=session_id)


@mcp_server.prompt(
    "plan-team-activity",
    description="O'quvchilar soni va vaqtiga mos eng yaxshi jamoaviy o'yinni tanlash"
)
def prompt_activity(student_count: int, duration_minutes: int) -> str:
    return prompts.prompt_plan_team_activity(student_count=student_count, duration_minutes=duration_minutes)
