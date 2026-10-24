from typing import Any, Dict, List, Optional
from ..base import BaseGameMode, FormFactor, GameContext
from ..registry import register_game_mode
from ..scoring import ScoringEngine


@register_game_mode
class ClassicGameMode(BaseGameMode):
    """
    Standard Kahoot-style game mode.
    Fast-paced individual competition with linear speed decay and streak multiplier.
    """

    mode_id: str = "classic"
    display_name: str = "Classic Quiz"
    category: str = "individual_race"
    supported_form_factors: List[FormFactor] = [FormFactor.LIVE]
    settings_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "speed_bonus": {"type": "boolean", "default": True},
            "show_top_n": {"type": "integer", "default": 5},
            "confidence_wagering": {"type": "boolean", "default": False},
        },
    }

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state.setdefault("round_history", [])
        context.custom_state.setdefault("answered_count", 0)

    async def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        context.current_question = question
        context.custom_state["current_question_id"] = question.get("id")
        context.custom_state["answered_count"] = 0

    async def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        p_id = answer.get("participant_id")
        is_correct = bool(answer.get("is_correct", False))
        elapsed = answer.get("elapsed_seconds", 0.0)
        time_limit = answer.get("time_limit_seconds", 30.0)
        current_streak = answer.get("current_streak", 0)
        confidence = answer.get("confidence", "low")
        base_points = answer.get("base_points", 1000)

        speed_bonus = context.settings.get("speed_bonus", True)
        decay_type = context.settings.get("decay_type", "linear")

        score_res = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=base_points,
            elapsed_seconds=elapsed,
            time_limit_seconds=time_limit,
            current_streak=current_streak,
            confidence=confidence,
            speed_bonus=speed_bonus,
            decay_type=decay_type,
        )

        context.custom_state["answered_count"] = context.custom_state.get("answered_count", 0) + 1

        return {
            "is_correct": is_correct,
            "points_awarded": score_res.score,
            "streak": score_res.streak,
            "streak_multiplier": score_res.streak_multiplier,
            "time_factor": score_res.time_factor,
            "game_effects": {
                "on_fire": score_res.streak >= 3,
            },
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[Dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        if context.total_rounds > 0 and context.current_round >= context.total_rounds:
            return True
        return False

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        base_state = {
            "mode_id": self.mode_id,
            "current_round": context.current_round,
            "total_rounds": context.total_rounds,
            "answered_count": context.custom_state.get("answered_count", 0),
        }

        if role in ("host", "projector"):
            base_state["total_participants"] = len(context.participants)
            return base_state

        return base_state
