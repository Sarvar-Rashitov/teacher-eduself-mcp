"""
Speed Run Game Mode Plugin.
High-intensity race against the clock with time attack bonuses and penalties.
"""

from typing import Dict, Any
from apps.game_engine.base import BaseGameMode, GameContext, FormFactor
from apps.game_engine.registry import register_game_mode
from apps.game_engine.scoring import ScoringEngine


@register_game_mode("speed_run")
class SpeedRunGameMode(BaseGameMode):
    mode_id = "speed_run"
    display_name = "Vaqt Poygasi (Speed Run)"
    category = "Arcade"
    supported_form_factors = [FormFactor.LIVE, FormFactor.SOLO]
    settings_schema = {
        "type": "object",
        "properties": {
            "time_penalty_seconds": {"type": "integer", "default": 3},
            "rapid_multiplier": {"type": "number", "default": 1.25}
        }
    }

    def on_session_init(self, context: GameContext) -> None:
        context.custom_state["mode"] = "speed_run"
        context.custom_state["fastest_answers"] = []

    def on_question_opened(self, question: Dict[str, Any], context: GameContext) -> None:
        pass

    def on_answer_submitted(self, answer: Dict[str, Any], context: GameContext) -> Dict[str, Any]:
        is_correct = answer.get("is_correct", False)
        base_points = answer.get("base_points", 1000)
        time_rem = answer.get("time_remaining", 0)
        total_time = answer.get("total_time", 30)

        points, _ = ScoringEngine.calculate_score(
            is_correct=is_correct,
            base_points=base_points,
            time_remaining=time_rem,
            total_time=total_time,
            streak=answer.get("streak", 0),
            speed_decay_enabled=True
        )

        # Agar tezkor javob bo'lsa (vaqtning 75%+ qismi qolgan bo'lsa)
        rapid_bonus = 0
        if is_correct and total_time > 0 and (time_rem / total_time) >= 0.75:
            rapid_bonus = int(points * 0.25)
            points += rapid_bonus

        time_penalty = 0
        if not is_correct:
            time_penalty = context.settings.get("time_penalty_seconds", 3)

        return {
            "is_correct": is_correct,
            "points_awarded": points,
            "rapid_bonus": rapid_bonus,
            "time_penalty_seconds": time_penalty,
            "time_remaining": time_rem
        }

    def serialize_state_for_role(self, role: str, context: GameContext) -> Dict[str, Any]:
        return {
            "mode": "speed_run",
            "time_penalty_seconds": context.settings.get("time_penalty_seconds", 3)
        }
