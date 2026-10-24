from typing import Optional, Any
from apps.game_engine.base import BaseGameMode, BaseGameModePlugin, GameContext, FormFactor
from apps.game_engine.registry import register_game_mode


@register_game_mode("speed_run")
class SpeedRunModePlugin(BaseGameModePlugin):
    """
    Speed Run Mode (Solo / Time Attack).
    Participants answer questions as rapidly as possible to achieve
    the lowest elapsed completion time with maximum accuracy.
    """

    mode_id = "speed_run"
    display_name = "Speed Run Time Attack"
    category = "solo_time_attack"
    supported_form_factors = [FormFactor.SOLO, FormFactor.LIVE]
    settings_schema = {
        "type": "object",
        "properties": {
            "time_penalty_per_mistake_sec": {"type": "integer", "default": 5},
        },
    }

    async def on_session_init(self, context: GameContext) -> None:
        context.custom_state["total_time_spent_ms"] = {}
        context.custom_state["correct_counts"] = {}
        context.custom_state["mistake_counts"] = {}

    async def on_question_opened(self, question: dict[str, Any], context: GameContext) -> None:
        pass

    async def on_answer_submitted(self, answer: dict[str, Any], context: GameContext) -> dict[str, Any]:
        participant_id = answer["participant_id"]
        time_taken_ms = answer.get("time_taken_ms", 1000)
        is_correct = answer.get("is_correct", False)
        penalty_sec = context.settings.get("time_penalty_per_mistake_sec", 5)

        prev_time = context.custom_state["total_time_spent_ms"].get(participant_id, 0)
        additional_penalty = 0 if is_correct else (penalty_sec * 1000)
        new_total_time = prev_time + time_taken_ms + additional_penalty
        context.custom_state["total_time_spent_ms"][participant_id] = new_total_time

        if is_correct:
            context.custom_state["correct_counts"][participant_id] = (
                context.custom_state["correct_counts"].get(participant_id, 0) + 1
            )
        else:
            context.custom_state["mistake_counts"][participant_id] = (
                context.custom_state["mistake_counts"].get(participant_id, 0) + 1
            )

        return {
            "participant_id": participant_id,
            "is_correct": is_correct,
            "time_taken_ms": time_taken_ms,
            "penalty_added_ms": additional_penalty,
            "total_elapsed_ms": new_total_time,
            "correct_count": context.custom_state["correct_counts"].get(participant_id, 0),
        }

    async def on_tick(self, delta_ms: int, context: GameContext) -> Optional[dict[str, Any]]:
        return None

    def check_end_condition(self, context: GameContext) -> bool:
        if context.total_rounds > 0 and context.current_round >= context.total_rounds:
            return True
        return False

    def serialize_state_for_role(self, role: str, context: GameContext) -> dict[str, Any]:
        elapsed = context.custom_state.get("total_time_spent_ms", {})
        # Lowest elapsed time ranks highest
        ranked = sorted(elapsed.items(), key=lambda x: x[1])
        return {
            "mode": self.mode_id,
            "leaderboard": [
                {
                    "rank": idx + 1,
                    "participant_id": p_id,
                    "total_ms": ms,
                    "correct": context.custom_state.get("correct_counts", {}).get(p_id, 0),
                }
                for idx, (p_id, ms) in enumerate(ranked)
            ],
        }
