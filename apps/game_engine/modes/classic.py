"""
Classic Quiz Game Mode Plugin (Kahoot style).
Spetsifikatsiya: .docs/engine/GAME_MODES.md (1-rejim)
"""
from typing import Optional, Dict, Any
from apps.game_engine.base import BaseGameModePlugin, FormFactor, GameContext
from apps.game_engine.registry import register_game_mode
from apps.game_engine.scoring import ScoringEngine


@register_game_mode("classic")
class ClassicModePlugin(BaseGameModePlugin):
    mode_id = "classic"
    display_name = "Klassik Viktorina (Classic Quiz)"
    category = "individual_competitive"
    supported_form_factors = [FormFactor.LIVE, FormFactor.SOLO]
    settings_schema = {
        "type": "object",
        "properties": {
            "speed_decay": {"type": "boolean", "default": True},
            "show_leaderboard_between": {"type": "boolean", "default": True}
        }
    }

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state["mode"] = "classic"
        context.custom_state["total_answers"] = 0
        context.custom_state["correct_answers"] = 0

    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.current_question = question

    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        is_correct = answer.get("is_correct", False)
        base_points = answer.get("base_points", ScoringEngine.DEFAULT_BASE_POINTS)
        time_elapsed = answer.get("time_elapsed")
        time_limit = answer.get("time_limit")
        streak = answer.get("streak", 0)

        calc = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=base_points,
            time_elapsed=time_elapsed,
            time_limit=time_limit,
            streak=streak,
            scoring_mode="speed_accuracy"
        )

        context.custom_state["total_answers"] = context.custom_state.get("total_answers", 0) + 1
        if is_correct:
            context.custom_state["correct_answers"] = context.custom_state.get("correct_answers", 0) + 1

        return {
            "is_correct": is_correct,
            "points_awarded": calc["points_awarded"],
            "streak": calc["streak"],
            "speed_multiplier": calc["speed_multiplier"],
            "streak_multiplier": calc["streak_multiplier"]
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        if context.total_rounds > 0 and context.current_round >= context.total_rounds:
            return True
        return False

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        if role == "projector":
            return {
                "mode": self.mode_id,
                "current_round": context.current_round,
                "total_rounds": context.total_rounds,
                "total_answers": context.custom_state.get("total_answers", 0),
            }
        elif role == "host":
            return {
                "mode": self.mode_id,
                "stats": context.custom_state,
                "current_round": context.current_round,
            }
        else:  # student
            return {
                "mode": self.mode_id,
                "current_round": context.current_round,
            }
