"""
Speed Run Game Mode Plugin.
Spetsifikatsiya: .docs/engine/GAME_MODES.md (Speedway Racing & Arkada)
"""
from typing import Optional, Dict, Any
from apps.game_engine.base import BaseGameModePlugin, FormFactor, GameContext
from apps.game_engine.registry import register_game_mode
from apps.game_engine.scoring import ScoringEngine


@register_game_mode("speed_run")
class SpeedRunModePlugin(BaseGameModePlugin):
    mode_id = "speed_run"
    display_name = "Vaqt Poygasi (Speed Run)"
    category = "individual_speed"
    supported_form_factors = [FormFactor.LIVE, FormFactor.SOLO]
    settings_schema = {
        "type": "object",
        "properties": {
            "fast_response_bonus": {"type": "boolean", "default": True}
        }
    }

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state["mode"] = "speed_run"
        context.custom_state["fast_answers_count"] = 0

    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.current_question = question

    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        is_correct = answer.get("is_correct", False)
        base_points = answer.get("base_points", ScoringEngine.DEFAULT_BASE_POINTS)
        time_elapsed = answer.get("time_elapsed", 0.0)
        time_limit = answer.get("time_limit", 10.0)
        streak = answer.get("streak", 0)

        calc = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=base_points,
            time_elapsed=time_elapsed,
            time_limit=time_limit,
            streak=streak,
            scoring_mode="speed_accuracy"
        )

        pts = calc["points_awarded"]
        bonus = 0
        # 25% dan kamroq vaqt ichida javob berilsa +200 tezlik bonusi
        if is_correct and time_elapsed and time_limit and (time_elapsed <= time_limit * 0.25):
            bonus = 200
            pts += bonus
            context.custom_state["fast_answers_count"] = context.custom_state.get("fast_answers_count", 0) + 1

        return {
            "is_correct": is_correct,
            "points_awarded": pts,
            "speed_bonus": bonus,
            "streak": calc["streak"],
            "speed_multiplier": calc["speed_multiplier"]
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        return context.total_rounds > 0 and context.current_round >= context.total_rounds

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        return {
            "mode": self.mode_id,
            "current_round": context.current_round,
            "total_rounds": context.total_rounds,
            "fast_answers_count": context.custom_state.get("fast_answers_count", 0)
        }
