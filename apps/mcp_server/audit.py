"""
Audit Logging and Security Traceability for EduSelf MCP Server.
Conforms to DOC-86 (MCP_SECURITY.md).
"""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional
from django.utils import timezone


logger = logging.getLogger("mcp_server.audit")

# Xotirada va testlarda tekshirish uchun so'nggi audit yozuvlari buferi
_in_memory_audit_logs: List[Dict[str, Any]] = []
MAX_AUDIT_LOGS = 1000


def hash_arguments(arguments: Any) -> str:
    """Argumentlar xeshini hosil qiladi (maxfiy ma'lumotlarni ochiq saqlamaslik uchun)."""
    try:
        serialized = json.dumps(arguments, sort_keys=True, default=str)
    except Exception:
        serialized = str(arguments)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def log_mcp_action(
    tool_name: str,
    teacher_id: Optional[str],
    client_name: str,
    arguments: Any,
    status: str,
    execution_time_ms: int,
    error_message: Optional[str] = None
) -> Dict[str, Any]:
    """MCP tool chaqiruvini audit jurnaliga yozadi."""
    record = {
        "timestamp": timezone.now().isoformat(),
        "client_name": client_name or "unknown",
        "teacher_id": str(teacher_id) if teacher_id else None,
        "tool_name": tool_name,
        "arguments_hash": hash_arguments(arguments),
        "status": status,
        "execution_time_ms": execution_time_ms,
        "error_message": error_message,
    }

    _in_memory_audit_logs.append(record)
    if len(_in_memory_audit_logs) > MAX_AUDIT_LOGS:
        _in_memory_audit_logs.pop(0)

    log_level = logging.INFO if status == "SUCCESS" else logging.WARNING
    logger.log(
        log_level,
        "MCP Audit: tool=%s teacher=%s client=%s status=%s time=%dms",
        tool_name, teacher_id, client_name, status, execution_time_ms
    )
    return record


def get_recent_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """So'nggi audit yozuvlarini qaytaradi."""
    return list(reversed(_in_memory_audit_logs[-limit:]))


def clear_audit_logs():
    """Testlar uchun audit yozuvlarini tozalaydi."""
    _in_memory_audit_logs.clear()
