"""
System Resources Specification (eduself://...).
Conforms to DOC-83 (MCP_RESOURCES.md).
"""

import json
import uuid
from typing import Any, Dict, Optional

from apps.questions_registry.registry import question_type_registry
from apps.game_engine.registry import game_mode_registry
from apps.live_sessions.models import LiveSession
from apps.live_sessions.services import LiveSessionService

from .auth import get_current_mcp_context
from .scopes import require_scope, SCOPE_SESSION_READ
from .exceptions import MCPNotFoundError, MCPForbiddenError, MCPInvalidParamsError


def read_question_types_resource() -> str:
    """
    URI: eduself://question-types
    Platformadagi barcha savol turlari va ularning texnik qoidalarini qaytaradi.
    """
    types_catalog = question_type_registry.list_types()
    return json.dumps({
        "resource": "eduself://question-types",
        "total_types": len(types_catalog),
        "question_types": types_catalog,
    }, indent=2, ensure_ascii=False)


def read_game_modes_resource() -> str:
    """
    URI: eduself://game-modes
    Platformadagi barcha o'yin rejimlari, ularning g'alaba shartlari va form-faktorlarini qaytaradi.
    """
    modes_catalog = game_mode_registry.list_modes()
    return json.dumps({
        "resource": "eduself://game-modes",
        "total_modes": len(modes_catalog),
        "game_modes": modes_catalog,
    }, indent=2, ensure_ascii=False)


def read_teacher_guide_resource() -> str:
    """
    URI: eduself://teacher-guide
    Darsda interaktiv viktorinalarni o'tkazish bo'yicha metodik qo'llanma.
    """
    guide = """# EduSelf O'qituvchi Metodik Qo'llanmasi

## 1. Darsda Viktorina O'tkazishning Oltin Qoidalari
- **Tayyorgarlik:** Dars boshlanishidan oldin 5-10 ta sifatli savoldan iborat viktorina loyihasini oching.
- **Vaqt Taqsimoti:** 1 ta savol uchun 20-30 soniya vaqt ajratish tavsiya etiladi.
- **Formatlar Xilma-xilligi:** Dars davomida faqat bitta variantli test emas, balki tartiblash (Ordering) va kategoriyalash (Categorization) savollaridan ham foydalaning.

## 2. O'yin Rejimini Tanlash
- **Classic Mode:** Individual bilim va tezkorlikni baholash uchun.
- **Team Battle:** Sinfda birdamlik va jamoaviy muhit yaratish uchun.
- **Speed Run:** Dars oxiridagi 5 daqiqalik tezkor mustahkamlash uchun.
- **Gold Quest:** Tasodifiy qutilar va strategik ball o'g'irlash orqali o'quvchilarda qiziqish uyg'otish uchun.

## 3. Natijalar Tahlili
- Savol tugagach, to'g'ri javobni oshkor qilish (`reveal_answers`) orqali o'quvchilarga tushuntirish bering.
- Dars so'ngida `get_session_report` orqali sinfning eng katta bo'shliqlarini aniqlang va keyingi darsga `generate_followup_activity` bilan tayyorlaning.
"""
    return guide


def read_session_summary_resource(session_id: str) -> str:
    """
    URI: eduself://session/{session_id}/summary
    Jonli sessiyaning joriy holati va tahliliy xulosasi.
    Scope: session:read
    """
    context = get_current_mcp_context()
    try:
        session_uuid = uuid.UUID(str(session_id))
    except (ValueError, TypeError):
        raise MCPInvalidParamsError(f"Yaroqsiz session_id: {session_id}")

    session = LiveSession.objects.filter(id=session_uuid).select_related("quiz", "host").first()
    if not session:
        raise MCPNotFoundError(f"Sessiya topilmadi: {session_id}")

    if context and context.user and session.host_id != context.user.id and not context.user.is_superuser:
        raise MCPForbiddenError("Boshqa o'qituvchining sessiyasini ko'rish taqiqlangan!")

    snapshot = LiveSessionService.get_state_snapshot(session=session, is_host=True)
    return json.dumps(snapshot, indent=2, ensure_ascii=False, default=str)
