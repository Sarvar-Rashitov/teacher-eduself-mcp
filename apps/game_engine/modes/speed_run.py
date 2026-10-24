from typing import Any, Dict, List, Optional
from ..base import BaseGameMode, FormFactor, GameContext
from ..registry import register_game_mode
from ..scoring import ScoringEngine


@register_game_mode
class SpeedRunGameMode(BaseGameMode):
    """
    Speed Run Game Mode.
    Intense time-attack mode where sub-3-second answers award combo speed boosts,
    and incorrect answers apply small time/score freeze penalties.
    """

    mode_id: str = "speed_run"
    display_name: str = "Speed Run"
    category: str = "arcade_race"
    supported_form_factors: List[FormFactor] = [FormFactor.LIVE, FormFactor.SOLO]
    settings_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "turbo_threshold_seconds": {"type": "number", "default": 3.0},
            "turbo_bonus_multiplier": {"type": "number", "default": 1.25},
        },
    }

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state.setdefault("combos", {})

    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.current_question = question

    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        p_id = str(answer.get("participant_id"))
        is_correct = bool(answer.get("is_correct", False))
        elapsed = float(answer.get("elapsed_seconds", 0.0))
        time_limit = float(answer.get("time_limit_seconds", 15.0))
        current_streak = int(answer.get("current_streak", 0))

        turbo_threshold = float(context.settings.get("turbo_threshold_seconds", 3.0))
        turbo_bonus = float(context.settings.get("turbo_bonus_multiplier", 1.25))

        # Base score
        score_res = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=answer.get("base_points", 1000),
            elapsed_seconds=elapsed,
            time_limit_seconds=time_limit,
            current_streak=current_streak,
            speed_bonus=True,
        )

        final_points = score_res.score
        is_turbo = False
        if is_correct and elapsed <= turbo_threshold:
            is_turbo = True
            final_points = int(round(final_points * turbo_bonus))

        return {
            "is_correct": is_correct,
            "points_awarded": final_points,
            "streak": score_res.streak,
            "is_turbo": is_turbo,
            "game_effects": {
                "turbo_boost": is_turbo,
                "freeze_penalty": not is_correct,
            },
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        return context.total_rounds > 0 and context.current_round >= context.total_rounds

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        return {
            "mode_id": self.mode_id,
            "current_round": context.current_round,
            "total_rounds": context.total_rounds,
        }
