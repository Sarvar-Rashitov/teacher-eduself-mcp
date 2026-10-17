# ============================================================
# EduSelf Teacher — apps/mcp_server/resources.py
# System Resources Catalog for MCP
# MCP_RESOURCES.md DOC-83 asosida
# ============================================================
import json
from asgiref.sync import sync_to_async
import apps.game_engine.modes  # auto-register core plugins
from apps.questions_registry.registry import question_registry
from apps.game_engine.registry import game_mode_registry
from apps.live_sessions.models import LiveSession
from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.scopes import has_scope, SCOPE_SESSION_READ
from apps.mcp_server.exceptions import MCPResourceNotFoundError, MCPForbiddenError


TEACHER_GUIDE_MARKDOWN = """# EduSelf O'qituvchi Metodik Qo'llanmasi

## 1. Darsda Viktorinalardan Samarali Foydalanish
- **Mavzuni kiritish (Warm-up):** Dars boshida 3-5 ta qisqa Single Choice yoki True/False savollari bilan o'quvchilar diqqatini jamlang.
- **Formativ baholash:** Mavzu o'rtasida Categorization yoki Ordering formatidagi amaliy savollar bering.
- **Mustahkamlash va Yakun:** Jamoaviy rejimlar (Team Battle, Gold Quest) orqali o'quvchilarda jamoaviy ruh va qiziqishni oshiring.

## 2. Vaqt Chegaralari
- Oddiy savollar: 15-20 soniya.
- Murakkab mantiqiy yoki tartiblash savollari: 30-45 soniya.
- Dars davomiyligi 45 daqiqa bo'lsa, 10-15 ta savoldan oshirmaslik tavsiya etiladi.
"""


def get_question_types_resource() -> str:
    """Barcha savol turlari va ularning metadata sxemalarini qaytaradi."""
    types = question_registry.list_types()
    return json.dumps({
        "total_types": len(types),
        "question_types": types
    }, ensure_ascii=False, indent=2)


def get_game_modes_resource() -> str:
    """Platformadagi barcha o'yin rejimlari va ularning parametrlarini qaytaradi."""
    modes = game_mode_registry.list_modes()
    return json.dumps({
        "total_modes": len(modes),
        "game_modes": modes
    }, ensure_ascii=False, indent=2)


def get_teacher_guide_resource() -> str:
    """Interaktiv viktorinalarni o'tkazish bo'yicha metodik qo'llanma."""
    return TEACHER_GUIDE_MARKDOWN


@sync_to_async
def get_session_summary_resource_sync(session_id: str, user, user_scopes: list) -> str:
    if not has_scope(user_scopes, SCOPE_SESSION_READ):
        raise MCPForbiddenError("Sessiya resursini ko'rish uchun 'session:read' ruxsati zarur.")

    try:
        session = LiveSession.objects.select_related('quiz', 'host').prefetch_related('participants').get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    if session.host_id != user.id and user.role != 'school_admin':
        raise MCPForbiddenError("Boshqa o'qituvchining sessiyasi resursini ko'rish taqiqlangan.")

    participants = list(session.participants.all())
    return json.dumps({
        "session_id": str(session.id),
        "room_code": session.room_code,
        "status": session.status,
        "game_mode": session.game_mode,
        "quiz_title": session.quiz.title if session.quiz else "",
        "connected_count": sum(1 for p in participants if p.is_connected),
        "total_participants": len(participants),
    }, ensure_ascii=False, indent=2)


async def get_session_summary_resource(session_id: str) -> str:
    """Jonli sessiya xulosasi dinamik resursi."""
    ctx = get_current_mcp_context()
    return await get_session_summary_resource_sync(session_id, ctx.user, ctx.scopes)
