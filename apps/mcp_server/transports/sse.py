"""
HTTP Server-Sent Events (SSE) and JSON-RPC 2.0 Message Dispatcher.
Conforms to DOC-81 (MCP_SERVER.md) and DOC-87 (MCP_COMPATIBILITY.md).
"""

import json
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from ..server import mcp_server, execute_tool, REGISTERED_TOOLS
from ..resources import (
    read_question_types_resource,
    read_game_modes_resource,
    read_teacher_guide_resource,
    read_session_summary_resource,
)
from ..prompts import (
    get_create_lesson_quiz_prompt,
    get_analyze_session_report_prompt,
    get_plan_team_activity_prompt,
)
from ..exceptions import (
    MCPBaseError,
    MCPParseError,
    MCPInvalidRequestError,
    MCPMethodNotFoundError,
    MCPInvalidParamsError,
    MCPInternalError,
)


class JSONRPCDispatcher:
    """
    JSON-RPC 2.0 spetsifikatsiyasi bo'yicha kiruvchi xabarlarni tahlil qiladi va
    tegishli MCP metodlariga yo'naltiradi.
    """

    PROTOCOL_VERSION = "2024-11-05"

    @classmethod
    def handle_request(cls, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Bitta JSON-RPC 2.0 so'rovini qayta ishlaydi.
        Notification bo'lsa (id yo'q bo'lsa) None qaytarishi mumkin.
        """
        if not isinstance(payload, dict):
            return cls._make_error_response(None, MCPInvalidRequestError())

        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {})

        if not method or not isinstance(method, str):
            return cls._make_error_response(req_id, MCPInvalidRequestError("Method nomi ko'rsatilmagan."))

        # Notification tekshiruvi (masalan: notifications/initialized)
        if method.startswith("notifications/"):
            return None

        try:
            result = cls._dispatch(method, params)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }
        except MCPBaseError as ex:
            return cls._make_error_response(req_id, ex)
        except Exception as ex:
            return cls._make_error_response(req_id, MCPInternalError(str(ex)))

    @classmethod
    def _dispatch(cls, method: str, params: Dict[str, Any]) -> Any:
        if method == "initialize":
            return {
                "protocolVersion": cls.PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": True, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "eduself-teacher-mcp",
                    "version": "1.0.0",
                },
            }

        elif method == "ping":
            return {}

        elif method == "tools/list":
            tools_list = []
            for name, func in REGISTERED_TOOLS.items():
                desc = func.__doc__.strip().split("\n")[0] if func.__doc__ else name
                is_destructive = name in ("start_session", "reveal_answers", "end_session")
                tools_list.append({
                    "name": name,
                    "description": desc,
                    "annotations": {
                        "destructiveHint": is_destructive,
                        "readOnlyHint": name.startswith("get_") or name.startswith("list_") or name.startswith("validate_"),
                    },
                })
            return {"tools": tools_list}

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if not tool_name:
                raise MCPInvalidParamsError("Tool nomi ('name') kiritilishi shart.")
            tool_res = execute_tool(tool_name, tool_args)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(tool_res, indent=2, ensure_ascii=False) if isinstance(tool_res, (dict, list)) else str(tool_res),
                    }
                ],
                "isError": False,
            }

        elif method == "resources/list":
            return {
                "resources": [
                    {
                        "uri": "eduself://question-types",
                        "name": "question-types",
                        "mimeType": "application/json",
                        "description": "EduSelf barcha savol turlari va ularning qoidalari",
                    },
                    {
                        "uri": "eduself://game-modes",
                        "name": "game-modes",
                        "mimeType": "application/json",
                        "description": "EduSelf barcha o'yin rejimlari va form-faktorlari",
                    },
                    {
                        "uri": "eduself://teacher-guide",
                        "name": "teacher-guide",
                        "mimeType": "text/markdown",
                        "description": "O'qituvchi interaktiv viktorinalar metodikasi",
                    },
                ]
            }

        elif method == "resources/read":
            uri = params.get("uri", "")
            if uri == "eduself://question-types":
                text = read_question_types_resource()
                mime = "application/json"
            elif uri == "eduself://game-modes":
                text = read_game_modes_resource()
                mime = "application/json"
            elif uri == "eduself://teacher-guide":
                text = read_teacher_guide_resource()
                mime = "text/markdown"
            elif uri.startswith("eduself://session/") and uri.endswith("/summary"):
                # uri: eduself://session/<session_id>/summary
                parts = uri.split("/")
                session_id = parts[3]
                text = read_session_summary_resource(session_id)
                mime = "application/json"
            else:
                raise MCPMethodNotFoundError(f"Resurs topilmadi: {uri}")

            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": mime,
                        "text": text,
                    }
                ]
            }

        elif method == "prompts/list":
            return {
                "prompts": [
                    {
                        "name": "create-lesson-quiz",
                        "description": "Dars mavzusi va sinfiga mos 10 ta savolli viktorina yaratish",
                        "arguments": [
                            {"name": "subject", "description": "Fan nomi", "required": True},
                            {"name": "grade", "description": "Sinf darajasi", "required": True},
                            {"name": "topic", "description": "Mavzu nomi", "required": False},
                        ],
                    },
                    {
                        "name": "analyze-session-report",
                        "description": "Sessiya natijalari bo'yicha sinf bo'shliqlarini tahlil qilish",
                        "arguments": [
                            {"name": "session_id", "description": "Sessiya ID", "required": True},
                        ],
                    },
                    {
                        "name": "plan-team-activity",
                        "description": "Sinf hajmi va dars vaqtiga mos jamoaviy rejim tanlash",
                        "arguments": [
                            {"name": "student_count", "description": "O'quvchilar soni", "required": True},
                            {"name": "duration_minutes", "description": "Dars vaqti daqiqada", "required": True},
                        ],
                    },
                ]
            }

        elif method == "prompts/get":
            name = params.get("name")
            p_args = params.get("arguments", {})
            if name == "create-lesson-quiz":
                content = get_create_lesson_quiz_prompt(
                    subject=p_args.get("subject", "Matematika"),
                    grade=str(p_args.get("grade", "7")),
                    topic=p_args.get("topic", ""),
                )
            elif name == "analyze-session-report":
                content = get_analyze_session_report_prompt(
                    session_id=p_args.get("session_id", ""),
                )
            elif name == "plan-team-activity":
                content = get_plan_team_activity_prompt(
                    student_count=int(p_args.get("student_count", 20)),
                    duration_minutes=int(p_args.get("duration_minutes", 15)),
                )
            else:
                raise MCPMethodNotFoundError(f"Prompt topilmadi: {name}")

            return {
                "description": f"Prompt: {name}",
                "messages": [
                    {
                        "role": "user",
                        "content": {"type": "text", "text": content},
                    }
                ],
            }

        else:
            raise MCPMethodNotFoundError(f"Metod mavjud emas: '{method}'")

    @classmethod
    def _make_error_response(cls, req_id: Any, error: MCPBaseError) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": error.to_dict(),
        }


def generate_openapi_spec() -> Dict[str, Any]:
    """
    ChatGPT Custom GPT Actions uchun 17 ta MCP toolning OpenAPI 3.1 spetsifikatsiyasini
    avtomatik generatsiya qiladi (DOC-87 MCP_COMPATIBILITY.md).
    """
    paths = {}
    for name, func in REGISTERED_TOOLS.items():
        doc = func.__doc__.strip().split("\n")[0] if func.__doc__ else name
        paths[f"/tools/{name}"] = {
            "post": {
                "operationId": name,
                "summary": doc,
                "responses": {
                    "200": {
                        "description": "Muvaffaqiyatli natija",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    }
                }
            }
        }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "EduSelf Teacher MCP Actions API",
            "version": "1.0.0",
            "description": "ChatGPT Custom Actions orqali EduSelf platformasini boshqarish interfeysi."
        },
        "servers": [{"url": "/mcp"}],
        "paths": paths,
    }
