"""
EduSelf Teacher Model Context Protocol (MCP) Server.
Registered with official Python MCP SDK (MCPServer / FastMCP).
Registers Core Tools, Resources, and Prompts according to DOC-81, DOC-82, and DOC-83.
"""

import json
from typing import Any, Dict, List, Optional

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None

from apps.questions_registry.registry import registry as questions_registry
from apps.game_engine.registry import game_mode_registry
from apps.live_sessions.models import LiveSession
from apps.mcp_server.auth import MCPAuthContextManager, get_current_mcp_context
from apps.mcp_server.exceptions import (
    MCPError,
    JSONRPCMethodNotFoundError,
    JSONRPCInvalidParamsError,
    JSONRPCInternalError,
)
from apps.mcp_server.tools import quiz_tools, session_tools, analytics_tools

# MCP Server instansiyasini e'lon qilish
if FastMCP:
    mcp_server = FastMCP(
        name="eduself-teacher-mcp",
        version="1.0.0",
        instructions="EduSelf Teacher Platform MCP Server - Real-time classroom gamification and AI assistant.",
    )
else:
    mcp_server = None


# Toollar lug'ati (Dispatcher uchun)
TOOL_REGISTRY: Dict[str, Any] = {
    # 1. Kontent va Viktorinalar
    "create_quiz_draft": quiz_tools.create_quiz_draft,
    "get_quiz": quiz_tools.get_quiz,
    "update_quiz": quiz_tools.update_quiz,
    "validate_quiz": quiz_tools.validate_quiz,
    "list_question_sets": quiz_tools.list_question_sets,
    "import_questions": quiz_tools.import_questions,
    # 2. Jonli Sessiyalar
    "create_live_session": session_tools.create_live_session,
    "get_session_status": session_tools.get_session_status,
    "start_session": session_tools.start_session,
    "advance_question": session_tools.advance_question,
    "reveal_answers": session_tools.reveal_answers,
    "end_session": session_tools.end_session,
    "get_live_results": session_tools.get_live_results,
    # 3. O'yinlar va Hisobotlar
    "create_team_game": analytics_tools.create_team_game,
    "get_session_report": analytics_tools.get_session_report,
    "generate_followup_activity": analytics_tools.generate_followup_activity,
}


def _register_tools_to_mcp(server_instance):
    """Barcha tool'larni rasmiy MCP server instansiyasiga ulash."""
    if not server_instance:
        return

    for tool_name, tool_func in TOOL_REGISTRY.items():
        is_destr = getattr(tool_func, "_is_destructive", False)
        # FastMCP / MCPServer da ro'yxatga olish
        server_instance.tool(
            name=tool_name,
            description=tool_func.__doc__ or tool_name,
        )(tool_func)


def _register_resources_to_mcp(server_instance):
    """DOC-83 bo'yicha tizim resurslarini ro'yxatga olish."""
    if not server_instance:
        return

    @server_instance.resource("eduself://question-types")
    def get_question_types_resource() -> str:
        """Barcha 29 ta canonical savol turlari va ularning JSON schemalari."""
        all_types = questions_registry.list_all()
        return json.dumps({"count": len(all_types), "question_types": all_types}, ensure_ascii=False, indent=2)

    @server_instance.resource("eduself://game-modes")
    def get_game_modes_resource() -> str:
        """Mavjud barcha o'yin rejimlari va form-faktorlar."""
        modes = game_mode_registry.list_all()
        return json.dumps({"count": len(modes), "game_modes": modes}, ensure_ascii=False, indent=2)

    @server_instance.resource("eduself://teacher-guide")
    def get_teacher_guide_resource() -> str:
        """Darsda interaktiv viktorinalarni o'tkazish bo'yicha metodik qo'llanma."""
        return (
            "# EduSelf O'qituvchi Qo'llanmasi\n\n"
            "1. Darsni boshlashdan oldin yangi viktorina draftini yarating (`create_quiz_draft`).\n"
            "2. Savollarni tekshiring (`validate_quiz`).\n"
            "3. Jonli xona oching (`create_live_session`) va PIN kodni proyektorda ko'rsating.\n"
            "4. O'quvchilar ulangach, darsni boshlang (`start_session`).\n"
            "5. Dars yakunlangach, tahlil hisobotini oling (`get_session_report`).\n"
        )

    @server_instance.resource("eduself://session/{session_id}/summary")
    def get_session_summary_resource(session_id: str) -> str:
        """Jonli sessiyaning joriy holati va natijalari xulosasi."""
        session = LiveSession.objects.filter(id=session_id).first()
        if not session:
            return json.dumps({"error": "Session not found"}, ensure_ascii=False)

        summary = {
            "session_id": str(session.id),
            "room_code": session.room_code,
            "status": session.status,
            "game_mode": session.game_mode,
            "participants_count": session.participants.count(),
            "current_question_index": session.current_question_index,
        }
        return json.dumps(summary, ensure_ascii=False, indent=2)


def _register_prompts_to_mcp(server_instance):
    """DOC-83 bo'yicha o'rnatilgan prompt shablonlarini ro'yxatga olish."""
    if not server_instance:
        return

    @server_instance.prompt("create-lesson-quiz")
    def create_lesson_quiz_prompt(subject: str, grade: int, topic: str = "") -> str:
        """O'qituvchi uchun dars viktorinasini yaratuvchi tayyor pedagogik prompt."""
        return (
            f"Siz EduSelf metodistisiz. {grade}-sinf o'quvchilari uchun '{subject}' fanidan "
            f"'{topic}' mavzusida 10 ta qiziqarli savoldan iborat viktorina tuzing. "
            "Savollar turli qiyinlik darajasida bo'lsin va 'create_quiz_draft' vositasi orqali saqlansin."
        )

    @server_instance.prompt("analyze-session-report")
    def analyze_session_report_prompt(session_id: str) -> str:
        """Sessiya natijalarini pedagogik tahlil qilish prompti."""
        return (
            f"Iltimos, '{session_id}' sessiyasi bo'yicha 'get_session_report' vositasini chaqiring "
            "va quyidagi 3 savolga javob bering:\n"
            "1. Sinf qaysi savollarda eng ko'p xato qildi?\n"
            "2. Qaysi o'quvchilarga qo'shimcha yordam kerak?\n"
            "3. Keyingi darsda qaysi mavzuni takrorlash tavsiya etiladi?"
        )

    @server_instance.prompt("plan-team-activity")
    def plan_team_activity_prompt(student_count: int, duration_minutes: int) -> str:
        """Sinfdagi o'quvchilar soni va dars vaqtiga mos jamoaviy rejimni tanlash."""
        return (
            f"Sinfda {student_count} nafar o'quvchi bor va o'yin uchun {duration_minutes} daqiqa ajratilgan. "
            "Eng ma'qul jamoaviy o'yin rejimini tavsiya qiling va 'create_team_game' vositasidan foydalaning."
        )


# Serverni to'liq sozlash
if mcp_server:
    _register_tools_to_mcp(mcp_server)
    _register_resources_to_mcp(mcp_server)
    _register_prompts_to_mcp(mcp_server)


def dispatch_tool(
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    user: Any = None,
    scopes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    JSON-RPC va HTTP kontrollerlari uchun markaziy asbob dispetcheri.
    Autentifikatsiya kontekstini ta'minlaydi va xatolarni standart formatga o'tkazadi.
    """
    if tool_name not in TOOL_REGISTRY:
        raise JSONRPCMethodNotFoundError(f"Asbob topilmadi: '{tool_name}'")

    func = TOOL_REGISTRY[tool_name]
    args = arguments or {}

    # Kontekst bilan bajarish
    if user:
        with MCPAuthContextManager(user=user, scopes=scopes or []):
            try:
                return func(**args)
            except TypeError as te:
                raise JSONRPCInvalidParamsError(f"Noto'g'ri parametrlar: {str(te)}")
    else:
        # Kontekst allaqachon tashqi tomondan o'rnatilgan bo'lsa
        try:
            return func(**args)
        except TypeError as te:
            raise JSONRPCInvalidParamsError(f"Noto'g'ri parametrlar: {str(te)}")
