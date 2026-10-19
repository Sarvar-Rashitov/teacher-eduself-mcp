"""
Core MCPServer Initialization and Feature Registration.
Conforms to DOC-80, DOC-81, DOC-82, DOC-83.
"""

import time
from typing import Any, Callable, Dict, Optional
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .audit import log_mcp_action
from .auth import get_current_mcp_context
from .exceptions import MCPBaseError, MCPMethodNotFoundError, MCPInternalError

# Tool imports
from .tools.quiz_tools import (
    create_quiz_draft,
    get_quiz,
    update_quiz,
    validate_quiz,
    import_questions,
    list_question_sets,
)
from .tools.session_tools import (
    create_live_session,
    get_session_status,
    start_session,
    advance_question,
    reveal_answers,
    end_session,
    get_live_results,
)
from .tools.analytics_tools import (
    create_team_game,
    create_anonymous_board,
    get_session_report,
    generate_followup_activity,
)

# Resource imports
from .resources import (
    read_question_types_resource,
    read_game_modes_resource,
    read_teacher_guide_resource,
    read_session_summary_resource,
)

# Prompt imports
from .prompts import (
    get_create_lesson_quiz_prompt,
    get_analyze_session_report_prompt,
    get_plan_team_activity_prompt,
)


# Markaziy MCPServer Nusxasi
mcp_server = MCPServer(
    name="eduself-teacher-mcp",
    version="1.0.0",
    description="EduSelf Teacher Model Context Protocol Server (Zero-Bypass Architecture)",
)

# 1. Kontent va Savollar Boshqaruvi Toollari (Tools 1–6)
mcp_server.add_tool(
    create_quiz_draft,
    name="create_quiz_draft",
    description="Berilgan parametrlar (fan, sinf, mavzu) asosida yangi viktorina draftini yaratadi.",
)

mcp_server.add_tool(
    get_quiz,
    name="get_quiz",
    description="Saqlangan viktorina va uning savollarini to'liq formatda olish.",
)

mcp_server.add_tool(
    update_quiz,
    name="update_quiz",
    description="Mavjud viktorina parametrlarini yoki savollarini tahrirlash.",
)

mcp_server.add_tool(
    validate_quiz,
    name="validate_quiz",
    description="Viktorinadagi savollarning to'liqligi va xatoliklarini tekshirish.",
)

mcp_server.add_tool(
    import_questions,
    name="import_questions",
    description="JSON, CSV yoki matn formatidagi savollarni tahlil qilib viktorinaga import qilish.",
)

mcp_server.add_tool(
    list_question_sets,
    name="list_question_sets",
    description="O'qituvchining saqlangan viktorinalari ro'yxatini qidirish va sahifalash.",
)

# 2. Jonli Sessiya Boshqaruvi Toollari (Tools 7–13)
mcp_server.add_tool(
    create_live_session,
    name="create_live_session",
    description="Tanlangan viktorina va o'yin rejimi bo'yicha yangi jonli sessiya (xona) ochish.",
)

mcp_server.add_tool(
    get_session_status,
    name="get_session_status",
    description="Jonli sessiyaning joriy holati, fazasi va ulangan o'quvchilar sonini olish.",
)

mcp_server.add_tool(
    start_session,
    name="start_session",
    description="Lobbini yopib, 1-savolni va jonli darsni boshlash (O'qituvchi tasdig'i talab qilinadi).",
    annotations=ToolAnnotations(destructive_hint=True),
)

mcp_server.add_tool(
    advance_question,
    name="advance_question",
    description="Keyingi savolga yoki natijalar fazasiga o'tish.",
)

mcp_server.add_tool(
    reveal_answers,
    name="reveal_answers",
    description="Savol vaqtini yakunlab, to'g'ri javobni oshkor qilish (O'qituvchi tasdig'i talab qilinadi).",
    annotations=ToolAnnotations(destructive_hint=True),
)

mcp_server.add_tool(
    end_session,
    name="end_session",
    description="Sessiyani yakunlash, yakuniy reytingni ko'rsatish va xonani yopish.",
    annotations=ToolAnnotations(destructive_hint=True),
)

mcp_server.add_tool(
    get_live_results,
    name="get_live_results",
    description="Joriy savol bo'yicha ishtirokchilar javoblari va natijalar statistikasini olish.",
)

# 3. O'yinlar va Hisobotlar Toollari (Tools 14–17)
mcp_server.add_tool(
    create_team_game,
    name="create_team_game",
    description="O'quvchilarni jamoalarga taqsimlab, jamoaviy o'yin rejimini faollashtirish.",
)

mcp_server.add_tool(
    create_anonymous_board,
    name="create_anonymous_board",
    description="Jonli sessiya uchun anonim fikrlar yoki savollar doskasini faollashtirish.",
)

mcp_server.add_tool(
    get_session_report,
    name="get_session_report",
    description="Sessiya yakunlangach, sinfning umumiy o'zlashtirishi va xatolar tahlilini olish.",
)

mcp_server.add_tool(
    generate_followup_activity,
    name="generate_followup_activity",
    description="O'quvchilar ko'p adashgan mavzular bo'yicha keyingi dars uchun mustahkamlovchi viktorina yaratish.",
)

# 4. Tizim Resurslari (MCP Resources)
mcp_server.resource(
    uri="eduself://question-types",
    name="question-types",
    title="EduSelf Savol Turlari Katalogi",
    description="Barcha mavjud savol turlari, ularning cheklovlari va JSON sxemalari.",
    mime_type="application/json",
)(read_question_types_resource)

mcp_server.resource(
    uri="eduself://game-modes",
    name="game-modes",
    title="EduSelf O'yin Rejimlari Katalogi",
    description="Barcha o'yin rejimlari, ularning qoidalari va tavsiflari.",
    mime_type="application/json",
)(read_game_modes_resource)

mcp_server.resource(
    uri="eduself://teacher-guide",
    name="teacher-guide",
    title="O'qituvchi Metodik Qo'llanmasi",
    description="Darsda interaktiv viktorinalarni samarali o'tkazish metodikasi.",
    mime_type="text/markdown",
)(read_teacher_guide_resource)

# 5. O'rnatilgan Prompt Shablonlari (MCP Prompts)
mcp_server.prompt(
    name="create-lesson-quiz",
    title="Dars Viktorinasi Yaratish",
    description="Dars mavzusi va sinf darajasiga mos 10 ta savolli viktorina yaratish.",
)(get_create_lesson_quiz_prompt)

mcp_server.prompt(
    name="analyze-session-report",
    title="Natijalarni Tahlil Qilish",
    description="Sessiya hisoboti asosida o'quvchilar bo'shliqlarini tahlil qilish va 3 ta tavsiya berish.",
)(get_analyze_session_report_prompt)

mcp_server.prompt(
    name="plan-team-activity",
    title="Jamoaviy Faoliyat Rejalashtirish",
    description="Sinf hajmi va vaqtiga mos eng yaxshi jamoaviy rejimni tanlash.",
)(get_plan_team_activity_prompt)


# Barcha ro'yxatga olingan toollar lug'ati (Tezkor qidiruv va tekshirish uchun)
REGISTERED_TOOLS: Dict[str, Callable] = {
    "create_quiz_draft": create_quiz_draft,
    "get_quiz": get_quiz,
    "update_quiz": update_quiz,
    "validate_quiz": validate_quiz,
    "import_questions": import_questions,
    "list_question_sets": list_question_sets,
    "create_live_session": create_live_session,
    "get_session_status": get_session_status,
    "start_session": start_session,
    "advance_question": advance_question,
    "reveal_answers": reveal_answers,
    "end_session": end_session,
    "get_live_results": get_live_results,
    "create_team_game": create_team_game,
    "create_anonymous_board": create_anonymous_board,
    "get_session_report": get_session_report,
    "generate_followup_activity": generate_followup_activity,
}


def execute_tool(tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
    """
    Asbobni xavfsiz audit jurnali va xatoliklar ishlovi bilan bajaradi.
    """
    if tool_name not in REGISTERED_TOOLS:
        raise MCPMethodNotFoundError(f"Asbob topilmadi: '{tool_name}'")

    func = REGISTERED_TOOLS[tool_name]
    args = arguments or {}

    context = get_current_mcp_context()
    teacher_id = str(context.user.id) if context and context.user else None
    client_name = context.client_name if context else "unknown"

    start_time = time.time()
    try:
        result = func(**args)
        duration_ms = int((time.time() - start_time) * 1000)
        log_mcp_action(
            tool_name=tool_name,
            teacher_id=teacher_id,
            client_name=client_name,
            arguments=args,
            status="SUCCESS",
            execution_time_ms=duration_ms,
        )
        return result
    except MCPBaseError as ex:
        duration_ms = int((time.time() - start_time) * 1000)
        log_mcp_action(
            tool_name=tool_name,
            teacher_id=teacher_id,
            client_name=client_name,
            arguments=args,
            status=ex.error_code,
            execution_time_ms=duration_ms,
            error_message=ex.message,
        )
        raise
    except Exception as ex:
        duration_ms = int((time.time() - start_time) * 1000)
        log_mcp_action(
            tool_name=tool_name,
            teacher_id=teacher_id,
            client_name=client_name,
            arguments=args,
            status="SERVER_ERROR",
            execution_time_ms=duration_ms,
            error_message=str(ex),
        )
        raise MCPInternalError(f"Asbobni bajarishda kutilmagan xatolik yuz berdi: {str(ex)}")
