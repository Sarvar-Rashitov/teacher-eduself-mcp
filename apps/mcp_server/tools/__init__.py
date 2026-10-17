# ============================================================
# EduSelf Teacher — apps/mcp_server/tools/__init__.py
# MCP Tools Export Registry
# ============================================================
from apps.mcp_server.tools.quiz_tools import (
    create_quiz_draft,
    get_quiz,
    update_quiz,
    validate_quiz,
    import_questions,
    list_question_sets,
    list_quizzes,
    create_quiz,
)

from apps.mcp_server.tools.session_tools import (
    create_live_session,
    get_session_status,
    start_session,
    advance_question,
    reveal_answers,
    end_session,
    get_live_results,
    start_live_session,
)

from apps.mcp_server.tools.analytics_tools import (
    create_team_game,
    create_anonymous_board,
    get_session_report,
    generate_followup_activity,
    export_results,
    get_quiz_analytics,
)

__all__ = [
    # Category 1: Quiz & Content
    "create_quiz_draft",
    "get_quiz",
    "update_quiz",
    "validate_quiz",
    "import_questions",
    "list_question_sets",
    "list_quizzes",
    "create_quiz",
    # Category 2: Live Session
    "create_live_session",
    "get_session_status",
    "start_session",
    "advance_question",
    "reveal_answers",
    "end_session",
    "get_live_results",
    "start_live_session",
    # Category 3: Games & Analytics
    "create_team_game",
    "create_anonymous_board",
    "get_session_report",
    "generate_followup_activity",
    "export_results",
    "get_quiz_analytics",
]
