"""
Classic Quiz Game Mode Plugin (Kahoot-style).
Individual competition with speed decay bonus and streak multiplier.
"""

from typing import Dict, Any, Optional
from apps.game_engine.base import BaseGameMode, GameContext, FormFactor
from apps.game_engine.registry import register_game_mode
from apps.game_engine.scoring import ScoringEngine


@register_game_mode("classic")
class ClassicGameMode(BaseGameMode):
    mode_id = "classic"
    display_name = "Klassik Viktorina (Classic Quiz)"
    category = "Classic"
    supported_form_factors = [FormFactor.LIVE, FormFactor.SOLO]
    settings_schema = {
        "type": "object",
        "properties": {
            "speed_decay": {"type": "boolean", "default": True},
            "streak_bonus": {"type": "boolean", "default": True},
            "show_leaderboard": {"type": "boolean", "default": True}
        }
    }

    def on_session_init(self, context: GameContext) -> None:
        context.custom_state["mode"] = "classic"
        context.custom_state["total_answers"] = 0

    def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.custom_state["question_id"] = question.get("id")
        context.custom_state["question_opened_at"] = question.get("deadline_ts")

    def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        is_correct = answer.get("is_correct", False)
        base_points = answer.get("base_points", 1000)
        time_rem = answer.get("time_remaining")
        total_time = answer.get("total_time")
        streak = answer.get("streak", 0)

        speed_enabled = context.settings.get("speed_decay", True)

        points, penalty = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=base_points,
            score_fraction=answer.get("score_fraction", 1.0),
            time_remaining=time_rem,
            total_time=total_time,
            streak=streak,
            speed_decay_enabled=speed_enabled
        )

        context.custom_state["total_answers"] = context.custom_state.get("total_answers", 0) + 1

        return {
            "is_correct": is_correct,
            "points_awarded": points,
            "penalty": penalty,
            "streak": streak + 1 if is_correct else 0,
            "game_effects": {"flame": streak >= 2 if is_correct else False}
        }

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        return {
            "mode": "classic",
            "total_answers": context.custom_state.get("total_answers", 0),
            "show_leaderboard": context.settings.get("show_leaderboard", True)
        }
