# ============================================================
# EduSelf Teacher — apps/mcp_server/transports/sse.py
# HTTP Server-Sent Events (SSE) Transport Engine
# MCP_SERVER.md DOC-81 asosida
# ============================================================
import asyncio
import json
import time
import logging
from typing import Dict, Optional, AsyncGenerator, Any

from apps.mcp_server.auth import MCPContext

logger = logging.getLogger(__name__)


class SSESessionManager:
    """
    Faol SSE ulanishlarini va xabarlar navbatlarini boshqaruvchi xizmat.
    """
    _sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, session_id: str, context: Optional[MCPContext] = None) -> None:
        cls._sessions[session_id] = {
            "queue": None,
            "context": context,
            "created_at": time.time(),
        }
        logger.info(f"[SSE] Yangi sessiya ro'yxatga olindi: {session_id}")

    @classmethod
    def set_queue(cls, session_id: str, queue: asyncio.Queue) -> None:
        if session_id in cls._sessions:
            cls._sessions[session_id]["queue"] = queue

    @classmethod
    def get_context(cls, session_id: str) -> Optional[MCPContext]:
        session_data = cls._sessions.get(session_id)
        return session_data.get("context") if session_data else None

    @classmethod
    async def push_message(cls, session_id: str, message: dict) -> bool:
        session_data = cls._sessions.get(session_id)
        if not session_data:
            return False
        queue = session_data.get("queue")
        if queue:
            await queue.put(message)
            return True
        return False

    @classmethod
    def remove(cls, session_id: str) -> None:
        if session_id in cls._sessions:
            del cls._sessions[session_id]
            logger.info(f"[SSE] Sessiya o'chirildi: {session_id}")


async def sse_event_stream(session_id: str, message_endpoint: str) -> AsyncGenerator[str, None]:
    """
    Server-Sent Events formatidagi ma'lumotlar oqimi generatori.
    - Dastlab `endpoint` hodisasini yuboradi.
    - Har 15 soniyada `: ping` keep-alive yuboradi.
    - Navbatdagi xabarlarni `event: message` ko'rinishida uzatadi.
    """
    queue: asyncio.Queue = asyncio.Queue()
    SSESessionManager.set_queue(session_id, queue)
    try:
        # 1. Dastlabki endpoint hodisasi
        yield f"event: endpoint\ndata: {message_endpoint}\n\n"

        while True:
            try:
                # 15 soniya davomida yangi xabar kutamiz
                msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                json_str = json.dumps(msg, ensure_ascii=False)
                yield f"event: message\ndata: {json_str}\n\n"
            except asyncio.TimeoutError:
                # Keep-Alive ping
                yield ": ping\n\n"
    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        SSESessionManager.remove(session_id)
